from __future__ import annotations

import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import ContextTypes, ConversationHandler

import db
from config import settings
from handlers.common import admin_keyboard, order_text
from payments.klikqris import KlikQRIS, KlikQRISError
from services.orders import new_order_id, rupiah
from services.channel_notifications import post_payment_claim, post_payment_proof

log = logging.getLogger(__name__)

WAIT_QTY, WAIT_PAY = range(2)


async def notify_admin(
    context_or_app,
    order_id: str,
    extra: str = "",
) -> None:
    order = db.order(order_id)
    if not order:
        return
    text = order_text(order)
    if extra:
        text += f"\n\n{extra}"
    bot = context_or_app.bot
    await bot.send_message(
        settings.admin_user_id,
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(order_id),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db.upsert_user(update.effective_user)
    await update.effective_message.reply_text(
        "Selamat datang! 👋",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🛍️ Lihat Produk", callback_data="catalog")]]
        ),
    )


async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    items = db.products()
    if not items:
        await query.edit_message_text("Belum ada produk yang tersedia.")
        return

    rows = [
        [
            InlineKeyboardButton(
                f"{item['name']} — {rupiah(item['price'])}",
                callback_data=f"p:{item['id']}",
            )
        ]
        for item in items
    ]
    await query.edit_message_text(
        "🛍️ <b>Pilih Produk</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split(":", 1)[1])
    item = db.product(product_id)
    if not item or not item["active"]:
        await query.edit_message_text("Produk tidak tersedia.")
        return ConversationHandler.END

    context.user_data["product_id"] = item["id"]
    await query.edit_message_text(
        f"📦 <b>{item['name']}</b>\n"
        f"{item['description']}\n\n"
        f"Harga: <b>{rupiah(item['price'])}</b>\n\n"
        "Kirim jumlah pembelian (1-100):",
        parse_mode="HTML",
    )
    return WAIT_QTY


async def receive_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        quantity = int(update.effective_message.text.strip())
        if not 1 <= quantity <= 100:
            raise ValueError
    except (TypeError, ValueError):
        await update.effective_message.reply_text("Jumlah harus berupa angka 1–100.")
        return WAIT_QTY

    item = db.product(context.user_data.get("product_id", 0))
    if not item or not item["active"]:
        await update.effective_message.reply_text("Produk sudah tidak tersedia.")
        context.user_data.clear()
        return ConversationHandler.END

    amount = int(item["price"]) * quantity
    context.user_data["quantity"] = quantity
    context.user_data["amount"] = amount

    buttons = []
    if settings.klikqris_enabled:
        buttons.append(
            [InlineKeyboardButton("⚡ QRIS Otomatis — KlikQRIS", callback_data="pay:k")]
        )
    buttons.append(
        [InlineKeyboardButton("📱 QRIS Manual — DANA", callback_data="pay:m")]
    )

    await update.effective_message.reply_text(
        f"{item['name']} x{quantity}\n"
        f"Total: <b>{rupiah(amount)}</b>\n\n"
        "Pilih metode pembayaran:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return WAIT_PAY


async def choose_payment(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    klikqris: KlikQRIS,
) -> int:
    query = update.callback_query
    await query.answer()

    item = db.product(context.user_data.get("product_id", 0))
    quantity = context.user_data.get("quantity")
    amount = context.user_data.get("amount")

    if not item or not quantity or not amount:
        await query.message.reply_text("Sesi pembelian sudah berakhir. Silakan /start lagi.")
        context.user_data.clear()
        return ConversationHandler.END

    order_id = new_order_id(query.from_user.id)
    method = "KLIKRIS" if query.data == "pay:k" else "MANUAL_DANA"

    db.create_order(
        order_id,
        query.from_user.id,
        item,
        int(quantity),
        int(amount),
        method,
    )

    if method == "KLIKRIS":
        if not settings.klikqris_enabled:
            db.cancel(order_id)
            await query.message.reply_text(
                "QRIS otomatis sedang tidak tersedia. Silakan pilih pembayaran manual."
            )
            context.user_data.clear()
            return ConversationHandler.END

        try:
            payment = await klikqris.create_transaction(
                order_id,
                int(amount),
                f"{item['name']} x{quantity}",
            )
            total_amount = int(float(payment["total_amount"]))

            db.update_payment(
                order_id,
                total_amount=total_amount,
                signature=str(payment["signature"]),
                qris_url=payment.get("qris_url"),
                direct_url=payment.get("direct_url"),
                expired_at=payment.get("expired_at"),
            )

            text = (
                f"🧾 <b>{order_id}</b>\n"
                f"📦 {item['name']} x{quantity}\n"
                f"💰 Nominal QRIS: <b>{rupiah(total_amount)}</b>\n\n"
                "Scan QRIS berikut. Status pembayaran akan diverifikasi otomatis."
            )

            qris_url = payment.get("qris_url")
            if qris_url:
                await query.message.reply_photo(
                    photo=qris_url,
                    caption=text,
                    parse_mode="HTML",
                )
            else:
                direct_url = payment.get("direct_url")
                if direct_url:
                    text += f"\n\n🔗 {direct_url}"
                await query.message.reply_text(text, parse_mode="HTML")

            await notify_admin(
                context,
                order_id,
                "Menunggu pembayaran otomatis KlikQRIS.",
            )
        except KlikQRISError:
            log.exception("Failed to create KlikQRIS transaction for %s", order_id)
            db.cancel(order_id)
            await query.message.reply_text(
                "QRIS otomatis gagal dibuat. Silakan ulangi pembelian dan pilih QRIS manual/DANA."
            )
    else:
        text = (
            f"🧾 <b>{order_id}</b>\n"
            f"📦 {item['name']} x{quantity}\n"
            f"💰 <b>{rupiah(amount)}</b>\n\n"
            f"📱 DANA: <code>{settings.dana_number or '-'}</code>\n"
            f"Nama: {settings.dana_name or '-'}\n\n"
            "Setelah melakukan pembayaran, tekan tombol di bawah atau kirim screenshot bukti pembayaran."
        )
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("✅ Saya Sudah Bayar", callback_data=f"manual:{order_id}")]]
        )

        if settings.manual_qris_image.exists():
            with settings.manual_qris_image.open("rb") as fh:
                await query.message.reply_photo(
                    InputFile(fh),
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
        else:
            await query.message.reply_text(
                text + "\n\n⚠️ Gambar QRIS manual belum dipasang.",
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        await notify_admin(
            context,
            order_id,
            "Menunggu konfirmasi pembayaran manual DANA.",
        )

    context.user_data.clear()
    return ConversationHandler.END


async def manual_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    order_id = query.data.split(":", 1)[1]
    order = db.order(order_id)
    if not order or order["telegram_id"] != query.from_user.id:
        return

    if order["status"] != "PENDING":
        await query.message.reply_text(
            f"Status order ini saat ini: {order['status']}."
        )
        return

    await query.message.reply_text(
        "Notifikasi sudah dikirim ke admin. Kirim screenshot bukti pembayaran jika diperlukan."
    )
    await notify_admin(
        context,
        order_id,
        "⚠️ Customer menekan tombol Saya Sudah Bayar.",
    )
    await post_payment_claim(context.bot, order)


async def payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message.photo:
        return

    order = db.latest_pending_for_user(update.effective_user.id)
    if not order:
        return

    file_id = update.effective_message.photo[-1].file_id
    db.add_proof(order["order_id"], file_id)

    await update.effective_message.reply_text(
        "📎 Bukti pembayaran diterima dan diteruskan untuk verifikasi."
    )

    # Keep the existing private admin notification.
    await context.bot.send_photo(
        settings.admin_user_id,
        file_id,
        caption=f"Bukti pembayaran {order['order_id']}",
    )

    # Also upload the original Telegram photo file_id to the transaction channel.
    # Telegram reuses the existing file, so no local download/re-upload is needed.
    await post_payment_proof(context.bot, order, file_id)

    await notify_admin(
        context,
        order["order_id"],
        "Ada bukti pembayaran baru. Bukti juga sudah diteruskan ke channel transaksi.",
    )
