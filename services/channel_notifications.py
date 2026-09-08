from __future__ import annotations

import html
import logging

from telegram import Bot
from telegram.error import TelegramError

from config import settings
from services.orders import rupiah

log = logging.getLogger(__name__)


def _mention(user_id: int, label: str) -> str:
    return f'<a href="tg://user?id={int(user_id)}">{html.escape(label)}</a>'


def owner_mention() -> str:
    # @username gives the most familiar Telegram mention behavior in channels.
    # If it is not configured, fall back to a clickable tg://user?id mention.
    if settings.owner_mention_username:
        return "@" + html.escape(settings.owner_mention_username)
    return _mention(settings.admin_user_id, settings.owner_mention_label)


def customer_mention(telegram_id: int) -> str:
    return _mention(telegram_id, f"Customer {telegram_id}")


def _base_caption(order, title: str) -> str:
    return (
        f"{title}\n\n"
        f"🧾 Order: <code>{html.escape(str(order['order_id']))}</code>\n"
        f"👤 Customer: {customer_mention(int(order['telegram_id']))}\n"
        f"📦 Produk: {html.escape(str(order['product_name']))} x{int(order['quantity'])}\n"
        f"💰 Total: <b>{rupiah(int(order['total_amount']))}</b>\n"
        f"💳 Metode: <b>{html.escape(str(order['payment_method']))}</b>\n"
        f"📌 Status: <b>{html.escape(str(order['status']))}</b>\n\n"
        f"🔔 Owner: {owner_mention()}"
    )


async def post_payment_proof(bot: Bot, order, file_id: str) -> bool:
    """Upload a customer's payment-proof image to the configured channel."""
    if not settings.payment_channel_id:
        return False

    try:
        await bot.send_photo(
            chat_id=settings.payment_channel_id,
            photo=file_id,
            caption=_base_caption(order, "📎 <b>BUKTI PEMBAYARAN BARU</b>"),
            parse_mode="HTML",
        )
        return True
    except TelegramError:
        log.exception(
            "Failed to upload payment proof for %s to channel %s",
            order["order_id"],
            settings.payment_channel_id,
        )
        return False


async def post_payment_verified(
    bot: Bot,
    order,
    *,
    source: str,
) -> bool:
    """Post an automatic/manual verified-payment record to the transaction channel."""
    if not settings.payment_channel_id:
        return False

    caption = _base_caption(order, "✅ <b>PEMBAYARAN TERVERIFIKASI</b>")
    caption += f"\n🔎 Verifikasi: <b>{html.escape(source)}</b>"

    try:
        await bot.send_message(
            chat_id=settings.payment_channel_id,
            text=caption,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except TelegramError:
        log.exception(
            "Failed to post verified payment %s to channel %s",
            order["order_id"],
            settings.payment_channel_id,
        )
        return False


async def post_payment_claim(bot: Bot, order) -> bool:
    """Record that a manual-payment customer pressed 'Saya Sudah Bayar'."""
    if not settings.payment_channel_id:
        return False

    caption = _base_caption(order, "⏳ <b>USER MENGAKU SUDAH BAYAR</b>")
    caption += "\n\nMenunggu bukti pembayaran / verifikasi admin."

    try:
        await bot.send_message(
            chat_id=settings.payment_channel_id,
            text=caption,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except TelegramError:
        log.exception(
            "Failed to post payment claim %s to channel %s",
            order["order_id"],
            settings.payment_channel_id,
        )
        return False
