from __future__ import annotations

import secrets
import time


def rupiah(value: int | float) -> str:
    return "Rp{:,.0f}".format(value).replace(",", ".")


def new_order_id(telegram_id: int) -> str:
    millis = int(time.time() * 1000)
    suffix = secrets.token_hex(2).upper()
    return f"INV-{telegram_id}-{millis}-{suffix}"
