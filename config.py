from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Local development can use .env or config.env.
# In Docker, variables from docker-compose env_file take precedence.
load_dotenv(".env", override=False)
load_dotenv("config.env", override=False)


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    admin_user_id: int

    public_base_url: str
    webhook_path: str

    klikqris_api_key: str
    klikqris_merchant_id: str
    klikqris_sandbox: bool

    dana_number: str
    dana_name: str
    manual_qris_image: Path

    db_path: Path
    log_file: Path
    log_level: str

    status_poll_seconds: int
    http_timeout_seconds: int

    host: str
    port: int

    @property
    def klikqris_enabled(self) -> bool:
        return bool(self.klikqris_api_key and self.klikqris_merchant_id)

    @property
    def klikqris_base_url(self) -> str:
        if self.klikqris_sandbox:
            return "https://klikqris.com/api/sandbox"
        return "https://klikqris.com/api"

    @property
    def callback_url(self) -> str:
        return f"{self.public_base_url}{self.webhook_path}"


def load_settings() -> Settings:
    webhook_path = os.getenv("WEBHOOK_PATH", "/webhook/klikqris").strip() or "/webhook/klikqris"
    if not webhook_path.startswith("/"):
        webhook_path = "/" + webhook_path

    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        admin_user_id=_int("ADMIN_USER_ID", 0),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/"),
        webhook_path=webhook_path,
        klikqris_api_key=os.getenv("KLIKRIS_API_KEY", "").strip(),
        klikqris_merchant_id=os.getenv("KLIKRIS_MERCHANT_ID", "").strip(),
        klikqris_sandbox=_bool("KLIKRIS_SANDBOX", True),
        dana_number=os.getenv("DANA_NUMBER", "").strip(),
        dana_name=os.getenv("DANA_NAME", "").strip(),
        manual_qris_image=Path(os.getenv("MANUAL_QRIS_IMAGE", "./data/dana_qris.png")),
        db_path=Path(os.getenv("DB_PATH", "./data/orders.db")),
        log_file=Path(os.getenv("LOG_FILE", "./logs/bot.log")),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        status_poll_seconds=max(15, _int("STATUS_POLL_SECONDS", 30)),
        http_timeout_seconds=max(5, _int("HTTP_TIMEOUT_SECONDS", 30)),
        host=os.getenv("HOST", "0.0.0.0").strip(),
        port=_int("PORT", 8080),
    )


def validate_settings(s: Settings) -> None:
    if not s.bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    if s.admin_user_id <= 0:
        raise RuntimeError("ADMIN_USER_ID must be a valid Telegram numeric user ID")

    has_key = bool(s.klikqris_api_key)
    has_merchant = bool(s.klikqris_merchant_id)
    if has_key != has_merchant:
        raise RuntimeError(
            "KLIKRIS_API_KEY and KLIKRIS_MERCHANT_ID must either both be set or both be empty"
        )

    if s.klikqris_enabled:
        if not s.public_base_url.startswith("https://"):
            raise RuntimeError(
                "PUBLIC_BASE_URL must start with https:// when KlikQRIS is enabled"
            )

    if not (1 <= s.port <= 65535):
        raise RuntimeError("PORT must be between 1 and 65535")


settings = load_settings()
