from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from telegram.ext import Application

import db
from config import settings
from handlers.user import notify_admin
from services.channel_notifications import post_payment_verified
from services.payment import (
    EXPIRED_STATUSES,
    SUCCESS_STATUSES,
    amount_from_payload,
    normalize_payload,
    normalize_status,
    signature_matches,
)

log = logging.getLogger(__name__)


def create_web_app(telegram_app: Application) -> FastAPI:
    app = FastAPI(
        title="AutoOrderTele",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.get("/health")
    async def health():
        db_ok = db.healthcheck()
        return JSONResponse(
            {
                "ok": db_ok,
                "database": "ok" if db_ok else "error",
                "klikqris": "enabled" if settings.klikqris_enabled else "disabled",
            },
            status_code=200 if db_ok else 503,
        )

    @app.post(settings.webhook_path)
    async def klikqris_webhook(request: Request):
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                {"ok": False, "error": "invalid_json"},
                status_code=400,
            )

        if not isinstance(payload, dict):
            return JSONResponse(
                {"ok": False, "error": "invalid_payload"},
                status_code=400,
            )

        data = normalize_payload(payload)
        order_id = str(data.get("order_id") or "").strip()
        status = normalize_status(data.get("status"))

        if not order_id:
            return JSONResponse(
                {"ok": False, "error": "missing_order_id"},
                status_code=400,
            )

        order = db.order(order_id)
        if not order:
            # Return 200 so KlikQRIS does not repeatedly retry an unknown local order.
            return {"ok": True, "ignored": "unknown_order"}

        if order["payment_method"] != "KLIKRIS":
            return {"ok": True, "ignored": "not_klikqris"}

        if order["status"] == "PAID":
            return {"ok": True, "ignored": "already_paid"}

        expected_signature = order["klik_signature"]
        if not signature_matches(expected_signature, data.get("signature")):
            log.warning("Rejected webhook with invalid signature: %s", order_id)
            return JSONResponse(
                {"ok": False, "error": "invalid_signature"},
                status_code=403,
            )

        if status in SUCCESS_STATUSES:
            try:
                paid_amount = amount_from_payload(data)
            except (TypeError, ValueError):
                return JSONResponse(
                    {"ok": False, "error": "invalid_amount"},
                    status_code=400,
                )

            if paid_amount is None or paid_amount != int(order["total_amount"]):
                log.warning(
                    "Amount mismatch for %s: expected=%s received=%s",
                    order_id,
                    order["total_amount"],
                    paid_amount,
                )
                return JSONResponse(
                    {"ok": False, "error": "amount_mismatch"},
                    status_code=400,
                )

            if db.mark_paid_if_pending(order_id, "KlikQRIS webhook"):
                await notify_admin(
                    telegram_app,
                    order_id,
                    "💸 Pembayaran KlikQRIS terverifikasi otomatis melalui webhook.",
                )
                await telegram_app.bot.send_message(
                    order["telegram_id"],
                    f"✅ Pembayaran <b>{order_id}</b> berhasil diverifikasi.",
                    parse_mode="HTML",
                )
                paid_order = db.order(order_id)
                if paid_order:
                    await post_payment_verified(
                        telegram_app.bot,
                        paid_order,
                        source="KlikQRIS webhook",
                    )

        elif status in EXPIRED_STATUSES:
            db.update_payment(order_id, status="EXPIRED")

        return {"ok": True}

    return app
