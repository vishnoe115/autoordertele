from __future__ import annotations

import logging

from telegram.ext import ContextTypes

import db
from handlers.user import notify_admin
from services.channel_notifications import post_payment_verified
from payments.klikqris import KlikQRIS
from services.payment import (
    EXPIRED_STATUSES,
    SUCCESS_STATUSES,
    amount_from_payload,
    normalize_status,
)

log = logging.getLogger(__name__)


def build_payment_checker(klikqris: KlikQRIS):
    async def check_payments(context: ContextTypes.DEFAULT_TYPE) -> None:
        if not klikqris.enabled:
            return

        for order in db.pending_auto_orders():
            try:
                data = await klikqris.check_status(order["order_id"])
                status = normalize_status(data.get("status"))

                if status in SUCCESS_STATUSES:
                    paid_amount = amount_from_payload(data)
                    if paid_amount != int(order["total_amount"]):
                        log.warning(
                            "Ignoring polling result with amount mismatch for %s",
                            order["order_id"],
                        )
                        continue

                    if db.mark_paid_if_pending(
                        order["order_id"],
                        "KlikQRIS status polling",
                    ):
                        await notify_admin(
                            context,
                            order["order_id"],
                            "💸 Pembayaran ditemukan oleh backup status polling.",
                        )
                        await context.bot.send_message(
                            order["telegram_id"],
                            f"✅ Pembayaran <b>{order['order_id']}</b> berhasil diverifikasi.",
                            parse_mode="HTML",
                        )
                        paid_order = db.order(order["order_id"])
                        if paid_order:
                            await post_payment_verified(
                                context.bot,
                                paid_order,
                                source="KlikQRIS status polling",
                            )

                elif status in EXPIRED_STATUSES:
                    db.update_payment(order["order_id"], status="EXPIRED")

            except Exception:
                log.exception(
                    "KlikQRIS polling failed for %s",
                    order["order_id"],
                )

    return check_payments
