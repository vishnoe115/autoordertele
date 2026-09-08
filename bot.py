from __future__ import annotations

import asyncio
import logging
import signal
import warnings

import uvicorn
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.warnings import PTBUserWarning

import db
from config import settings, validate_settings
from handlers import admin as admin_handlers
from handlers import user as user_handlers
from jobs.payment_checker import build_payment_checker
from logging_config import setup_logging
from payments.klikqris import KlikQRIS
from web.app import create_web_app

# This warning is expected for mixed MessageHandler + CallbackQueryHandler
# conversations. per_message=False is intentional.
warnings.filterwarnings(
    "ignore",
    message=r".*If 'per_message=False'.*CallbackQueryHandler.*",
    category=PTBUserWarning,
)

log = setup_logging()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error(
        "Unhandled Telegram update error",
        exc_info=(
            type(context.error),
            context.error,
            context.error.__traceback__,
        ) if context.error else None,
    )


def build_telegram_app(klikqris: KlikQRIS) -> Application:
    app = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .concurrent_updates(False)
        .build()
    )

    async def payment_callback(update, context):
        return await user_handlers.choose_payment(update, context, klikqris)

    purchase = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_handlers.select_product, pattern=r"^p:\d+$")
        ],
        states={
            user_handlers.WAIT_QTY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    user_handlers.receive_quantity,
                )
            ],
            user_handlers.WAIT_PAY: [
                CallbackQueryHandler(
                    payment_callback,
                    pattern=r"^pay:[km]$",
                )
            ],
        },
        fallbacks=[CommandHandler("start", user_handlers.start)],
        per_message=False,
        per_chat=True,
        per_user=True,
        conversation_timeout=600,
    )

    send_product = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                admin_handlers.send_start,
                pattern=r"^a:send:",
            )
        ],
        states={
            admin_handlers.SEND_PRODUCT: [
                MessageHandler(
                    filters.ALL & ~filters.COMMAND,
                    admin_handlers.send_product,
                )
            ]
        },
        fallbacks=[CommandHandler("admin", admin_handlers.admin)],
        per_message=False,
        per_chat=True,
        per_user=True,
    )

    add_product = ConversationHandler(
        entry_points=[
            CommandHandler("admin_add_product", admin_handlers.add_start)
        ],
        states={
            admin_handlers.ADD_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_handlers.add_name,
                )
            ],
            admin_handlers.ADD_DESC: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_handlers.add_description,
                )
            ],
            admin_handlers.ADD_PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_handlers.add_price,
                )
            ],
        },
        fallbacks=[CommandHandler("admin", admin_handlers.admin)],
        per_message=False,
        per_chat=True,
        per_user=True,
    )

    app.add_handler(CommandHandler("start", user_handlers.start))
    app.add_handler(CommandHandler("admin", admin_handlers.admin))
    app.add_handler(add_product)
    app.add_handler(send_product)
    app.add_handler(purchase)

    app.add_handler(
        CallbackQueryHandler(user_handlers.catalog, pattern=r"^catalog$")
    )
    app.add_handler(
        CallbackQueryHandler(user_handlers.manual_paid, pattern=r"^manual:")
    )
    app.add_handler(
        CallbackQueryHandler(admin_handlers.mark_paid, pattern=r"^a:paid:")
    )
    app.add_handler(
        CallbackQueryHandler(admin_handlers.cancel, pattern=r"^a:cancel:")
    )
    app.add_handler(
        CallbackQueryHandler(admin_handlers.orders, pattern=r"^a:orders$")
    )
    app.add_handler(
        CallbackQueryHandler(admin_handlers.products, pattern=r"^a:products$")
    )
    app.add_handler(
        MessageHandler(filters.PHOTO, user_handlers.payment_proof)
    )
    app.add_error_handler(error_handler)

    if settings.klikqris_enabled:
        checker = build_payment_checker(klikqris)
        app.job_queue.run_repeating(
            checker,
            interval=settings.status_poll_seconds,
            first=10,
            name="klikqris-payment-checker",
        )

    return app


async def run() -> None:
    validate_settings(settings)
    db.init()

    klikqris = KlikQRIS()
    telegram_app = build_telegram_app(klikqris)
    web_app = create_web_app(telegram_app)

    server = uvicorn.Server(
        uvicorn.Config(
            web_app,
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
            access_log=False,
        )
    )

    await telegram_app.initialize()
    await telegram_app.start()

    if telegram_app.updater is None:
        raise RuntimeError("Telegram updater is unavailable")

    await telegram_app.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )

    log.info(
        "Bot started | HTTP=%s:%s | KlikQRIS=%s | sandbox=%s",
        settings.host,
        settings.port,
        settings.klikqris_enabled,
        settings.klikqris_sandbox,
    )

    try:
        await server.serve()
    finally:
        log.info("Shutting down")
        if telegram_app.updater.running:
            await telegram_app.updater.stop()
        if telegram_app.running:
            await telegram_app.stop()
        await telegram_app.shutdown()
        await klikqris.close()


if __name__ == "__main__":
    asyncio.run(run())
