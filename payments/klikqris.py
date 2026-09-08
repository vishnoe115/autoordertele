from __future__ import annotations

import logging
from typing import Any

import httpx

from config import settings

log = logging.getLogger(__name__)


class KlikQRISError(RuntimeError):
    pass


class KlikQRIS:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": "autoordertele/2.0",
            },
        )

    @property
    def enabled(self) -> bool:
        return settings.klikqris_enabled

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": settings.klikqris_api_key,
            "id_merchant": settings.klikqris_merchant_id,
        }

    async def create_transaction(
        self,
        order_id: str,
        amount: int,
        description: str,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise KlikQRISError("KlikQRIS is not configured")

        payload = {
            "order_id": order_id,
            "id_merchant": settings.klikqris_merchant_id,
            "amount": int(amount),
            "keterangan": description[:200],
            "callback_url": settings.callback_url,
        }

        try:
            response = await self._client.post(
                f"{settings.klikqris_base_url}/qris/create",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise KlikQRISError(f"KlikQRIS create request failed: {exc}") from exc

        if not isinstance(body, dict) or body.get("status") is not True:
            message = body.get("message", "Unknown KlikQRIS error") if isinstance(body, dict) else "Invalid response"
            raise KlikQRISError(str(message))

        data = body.get("data")
        if not isinstance(data, dict):
            raise KlikQRISError("KlikQRIS response is missing data")

        required = ("order_id", "total_amount", "signature")
        missing = [key for key in required if data.get(key) in (None, "")]
        if missing:
            raise KlikQRISError(f"KlikQRIS response missing: {', '.join(missing)}")

        if str(data["order_id"]) != order_id:
            raise KlikQRISError("KlikQRIS returned an unexpected order_id")

        return data

    async def check_status(self, order_id: str) -> dict[str, Any]:
        if not self.enabled:
            raise KlikQRISError("KlikQRIS is not configured")

        try:
            response = await self._client.get(
                f"{settings.klikqris_base_url}/qris/status/{order_id}",
                headers=self._headers(),
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise KlikQRISError(f"KlikQRIS status request failed: {exc}") from exc

        if not isinstance(body, dict) or body.get("status") is not True:
            message = body.get("message", "Unknown KlikQRIS error") if isinstance(body, dict) else "Invalid response"
            raise KlikQRISError(str(message))

        data = body.get("data")
        if not isinstance(data, dict):
            raise KlikQRISError("KlikQRIS status response is missing data")
        return data

    async def close(self) -> None:
        await self._client.aclose()
