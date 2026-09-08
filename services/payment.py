from __future__ import annotations

import hmac
from typing import Any


SUCCESS_STATUSES = {"PAID", "SUCCESS"}
EXPIRED_STATUSES = {"EXPIRED"}


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return payload


def normalize_status(value: Any) -> str:
    return str(value or "").strip().upper()


def amount_from_payload(data: dict[str, Any]) -> int | None:
    value = data.get("total_amount")
    if value is None:
        value = data.get("amount_paid")
    if value is None:
        return None
    return int(float(value))


def signature_matches(expected: str | None, received: Any) -> bool:
    if not expected:
        return False
    if received is None:
        return False
    return hmac.compare_digest(str(expected), str(received))
