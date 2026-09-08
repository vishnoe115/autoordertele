from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import settings
from services.orders import rupiah


def admin_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Konfirmasi Pembayaran",
                    callback_data=f"a:paid:{order_id}",
                ),
                InlineKeyboardButton(
                    "❌ Batalkan",
                    callback_data=f"a:cancel:{order_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📦 Kirim Produk",
                    callback_data=f"a:send:{order_id}",
                )
            ],
        ]
    )


def order_text(order) -> str:
    return (
        f"🧾 <b>#{order['order_id']}</b>\n"
        f"👤 <code>{order['telegram_id']}</code>\n"
        f"📦 {order['product_name']} x{order['quantity']}\n"
        f"💰 <b>{rupiah(order['total_amount'])}</b>\n"
        f"💳 {order['payment_method']}\n"
        f"📌 <b>{order['status']}</b>"
    )


def is_admin(user_id: int | None) -> bool:
    return bool(user_id and user_id == settings.admin_user_id)
