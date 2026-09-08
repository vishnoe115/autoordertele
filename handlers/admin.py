from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

import db
from config import settings
from handlers.common import admin_keyboard, is_admin, order_text
from services.orders import rupiah
from services.channel_notifications import post_payment_verified

ADD_NAME, ADD_DESC, ADD_PRICE, SEND_PRODUCT = range(10, 14)


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return

    await update.effective_message.reply_text(
        "🔐 Admin Panel",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🧾 Order Terbaru", callback_data="a:orders")],
                [InlineKeyboardButton("📦 Produk", callback_data="a:products")],
            ]
        ),
    )


async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    rows = db.recent(10)
    if not rows:
        await query.message.reply_text("Belum ada order.")
        return

    for order in rows:
        await query.message.reply_text(
            order_text(order),
            parse_mode="HTML",
            reply_markup=admin_keyboard(order["order_id"]),
        )


async def products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    rows = db.products(active_only=False)
    text = "\n".join(
        f"#{item['id']} {item['name']} — {rupiah(item['price'])}"
        for item in rows
    )
    await query.message.reply_text(text or "Produk kosong.")


async def mark_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    order_id = query.data.split(":", 2)[2]
    changed = db.mark_paid_if_pending(order_id, "Admin confirmed")
    order = db.order(order_id)
    await query.edit_message_reply_markup(reply_markup=None)

    if not order:
        return

    if changed:
        await query.message.reply_text("✅ Payment confirmed.")
        await context.bot.send_message(
            order["telegram_id"],
            f"✅ Pembayaran diterima untuk <b>{order_id}</b>. Admin akan mengirim produk/detail.",
            parse_mode="HTML",
        )
        paid_order = db.order(order_id)
        if paid_order:
            await post_payment_verified(
                context.bot,
                paid_order,
                source="Manual confirmation by admin",
            )
    else:
        await query.message.reply_text(
            f"Order tidak diubah. Status saat ini: {order['status']}."
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    order_id = query.data.split(":", 2)[2]
    changed = db.cancel(order_id)
    order = db.order(order_id)
    await query.edit_message_reply_markup(reply_markup=None)

    if not order:
        return

    if changed:
        await query.message.reply_text("❌ Order dibatalkan.")
        await context.bot.send_message(
            order["telegram_id"],
            f"❌ Order <b>{order_id}</b> dibatalkan.",
            parse_mode="HTML",
        )
    else:
        await query.message.reply_text(
            f"Order tidak dapat dibatalkan. Status: {order['status']}."
        )


async def send_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    order_id = query.data.split(":", 2)[2]
    order = db.order(order_id)
    if not order:
        return ConversationHandler.END

    if order["status"] != "PAID":
        await query.message.reply_text("⚠️ Order belum PAID.")
        return ConversationHandler.END

    context.user_data["send_order_id"] = order_id
    await query.message.reply_text(
        f"📦 Kirim pesan/file/detail produk untuk {order_id}. "
        "Pesan berikutnya akan disalin ke customer."
    )
    return SEND_PRODUCT


async def send_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    order_id = context.user_data.get("send_order_id")
    order = db.order(order_id) if order_id else None
    if not order:
        context.user_data.clear()
        return ConversationHandler.END

    await update.effective_message.copy(chat_id=order["telegram_id"])
    await update.effective_message.reply_text("✅ Detail/produk terkirim.")
    context.user_data.clear()
    return ConversationHandler.END


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    await update.effective_message.reply_text("Nama produk:")
    return ADD_NAME


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_product_name"] = update.effective_message.text.strip()
    await update.effective_message.reply_text("Deskripsi produk:")
    return ADD_DESC


async def add_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_product_description"] = update.effective_message.text.strip()
    await update.effective_message.reply_text("Harga produk (angka saja):")
    return ADD_PRICE


async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = int(update.effective_message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text("Harga tidak valid.")
        return ADD_PRICE

    product_id = db.add_product(
        context.user_data["new_product_name"],
        context.user_data["new_product_description"],
        price,
    )
    context.user_data.clear()
    await update.effective_message.reply_text(
        f"✅ Produk #{product_id} berhasil ditambahkan."
    )
    return ConversationHandler.END
