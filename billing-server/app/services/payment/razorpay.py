"""
razorpay.py — Razorpay implementation of the PaymentProvider interface (Phase 2.3).
Handles async HTTP communication, retries with exponential backoff, HMAC signature verification,
and strict zero-secret logging.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from typing import Any
import httpx

from app.config import Settings
from app.services.exceptions import (
    PaymentProviderError,
    PaymentVerificationError,
    PaymentTimeoutError,
    PaymentRefundError,
)
from app.services.payment.provider import (
    PaymentProvider,
    PaymentOrderDTO,
    PaymentVerificationDTO,
    PaymentWebhookDTO,
    PaymentRefundDTO,
)

logger = logging.getLogger(__name__)


class RazorpayProvider(PaymentProvider):
    """
    Razorpay gateway integration client.
    Enforces strict zero-secret logging and explicit exception translation.
    Never calls SubscriptionService or ProvisioningService directly.
    """

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = settings.razorpay_base_url.rstrip("/")
        self.key_id = settings.razorpay_key_id
        self.key_secret = settings.razorpay_key_secret
        self.webhook_secret = settings.razorpay_webhook_secret
        self.timeout = settings.razorpay_timeout_seconds
        self.max_retries = settings.razorpay_max_retries
        self.orders_path = settings.razorpay_orders_path
        self.payments_path = settings.razorpay_payments_path
        self.refunds_path = settings.razorpay_refunds_path

        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(timeout=self.timeout)

    async def _request_with_retries(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute an HTTP request to Razorpay with exponential backoff retries for transient failures.
        Never logs API keys, authorization headers, or customer secrets.
        """
        url = f"{self.base_url}{path}"
        auth = (self.key_id, self.key_secret) if self.key_id and self.key_secret else None

        last_exception: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    json=json_data,
                    auth=auth,
                    timeout=self.timeout,
                )

                if response.status_code in (500, 502, 503, 504):
                    logger.warning(
                        "Transient Razorpay server error status=%d on attempt=%d/%d",
                        response.status_code,
                        attempt,
                        self.max_retries,
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(2 ** (attempt - 1))
                        continue
                    raise PaymentProviderError(
                        f"Razorpay server unavailable after {self.max_retries} attempts (status {response.status_code})"
                    )

                if response.status_code >= 400:
                    logger.error("Razorpay API error status=%d for path=%s", response.status_code, path)
                    try:
                        err_data = response.json()
                        err_msg = err_data.get("error", {}).get("description", "Unknown Razorpay error")
                    except Exception:
                        err_msg = f"HTTP {response.status_code} from Razorpay"
                    raise PaymentProviderError(f"Razorpay API request failed: {err_msg}")

                return response.json()

            except (httpx.TimeoutException, httpx.ConnectTimeout) as exc:
                last_exception = exc
                logger.warning(
                    "Timeout connecting to Razorpay on attempt=%d/%d",
                    attempt,
                    self.max_retries,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                raise PaymentTimeoutError(
                    f"Razorpay request timed out after {self.max_retries} attempts"
                ) from exc

            except httpx.RequestError as exc:
                last_exception = exc
                logger.warning(
                    "Network error connecting to Razorpay on attempt=%d/%d",
                    attempt,
                    self.max_retries,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                raise PaymentProviderError(
                    f"Network error communicating with Razorpay: {exc}"
                ) from exc

        raise PaymentProviderError("Failed to complete Razorpay request") from last_exception

    async def create_order(
        self,
        amount_minor_units: int,
        currency: str,
        receipt: str,
        notes: dict[str, str] | None = None,
    ) -> PaymentOrderDTO:
        """
        Create a new payment order in Razorpay.
        """
        payload = {
            "amount": amount_minor_units,
            "currency": currency.upper(),
            "receipt": receipt,
            "notes": notes or {},
        }
        logger.info("Creating Razorpay order receipt=%s amount=%d currency=%s", receipt, amount_minor_units, currency)
        data = await self._request_with_retries("POST", self.orders_path, json_data=payload)

        order_id = str(data.get("id", ""))
        if not order_id:
            raise PaymentProviderError("Razorpay order response missing order ID")

        return PaymentOrderDTO(
            provider_order_id=order_id,
            amount_minor_units=int(data.get("amount", amount_minor_units)),
            currency=str(data.get("currency", currency)),
            raw_data=data,
        )

    async def verify_webhook(
        self,
        payload: bytes | str,
        signature: str,
        secret: str | None = None,
    ) -> PaymentWebhookDTO:
        """
        Verify Razorpay webhook HMAC-SHA256 signature and parse payload.
        Never logs the secret or signature.
        """
        webhook_secret = secret or self.webhook_secret
        if not webhook_secret:
            raise PaymentVerificationError("Razorpay webhook secret is not configured")

        raw_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
        expected_sig = hmac.new(
            webhook_secret.encode("utf-8"),
            raw_bytes,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, signature):
            logger.error("Razorpay webhook HMAC signature mismatch")
            raise PaymentVerificationError("Invalid Razorpay webhook signature")

        try:
            data = json.loads(raw_bytes.decode("utf-8"))
        except Exception as exc:
            raise PaymentVerificationError("Malformed JSON in Razorpay webhook payload") from exc

        event_type = str(data.get("event", ""))
        payment_entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        order_entity = data.get("payload", {}).get("order", {}).get("entity", {})

        provider_payment_id = payment_entity.get("id")
        provider_order_id = payment_entity.get("order_id") or order_entity.get("id")
        status = payment_entity.get("status", event_type)
        amount = payment_entity.get("amount") or order_entity.get("amount")
        currency = payment_entity.get("currency") or order_entity.get("currency")

        logger.info("Verified Razorpay webhook event=%s status=%s", event_type, status)
        return PaymentWebhookDTO(
            event_type=event_type,
            status=str(status),
            provider_order_id=str(provider_order_id) if provider_order_id else None,
            provider_payment_id=str(provider_payment_id) if provider_payment_id else None,
            amount_minor_units=int(amount) if amount is not None else None,
            currency=str(currency) if currency else None,
            signature=signature,
            payload=data,
        )

    async def fetch_payment(
        self,
        provider_payment_id: str,
    ) -> PaymentVerificationDTO:
        """
        Fetch payment details from Razorpay to verify payment capture status.
        """
        path = self.payments_path.format(payment_id=provider_payment_id)
        logger.info("Fetching Razorpay payment status for payment_id=%s", provider_payment_id)
        data = await self._request_with_retries("GET", path)

        status = str(data.get("status", ""))
        is_valid = status in ("captured", "authorized")
        order_id = str(data.get("order_id", ""))

        return PaymentVerificationDTO(
            is_valid=is_valid,
            provider_order_id=order_id,
            provider_payment_id=provider_payment_id,
            status=status,
            amount_minor_units=int(data["amount"]) if "amount" in data else None,
            currency=str(data["currency"]) if "currency" in data else None,
            raw_data=data,
        )

    async def refund_payment(
        self,
        provider_payment_id: str,
        amount_minor_units: int | None = None,
        notes: dict[str, str] | None = None,
    ) -> PaymentRefundDTO:
        """
        Issue a refund for a captured Razorpay payment.
        """
        path = self.refunds_path.format(payment_id=provider_payment_id)
        payload: dict[str, Any] = {}
        if amount_minor_units is not None:
            payload["amount"] = amount_minor_units
        if notes:
            payload["notes"] = notes

        logger.info("Initiating Razorpay refund for payment_id=%s", provider_payment_id)
        try:
            data = await self._request_with_retries("POST", path, json_data=payload if payload else None)
        except PaymentProviderError as exc:
            raise PaymentRefundError(f"Failed to refund Razorpay payment: {exc}") from exc

        refund_id = str(data.get("id", ""))
        if not refund_id:
            raise PaymentRefundError("Razorpay refund response missing refund ID")

        return PaymentRefundDTO(
            provider_refund_id=refund_id,
            provider_payment_id=provider_payment_id,
            amount_minor_units=int(data.get("amount", amount_minor_units or 0)),
            status=str(data.get("status", "processed")),
            raw_data=data,
        )

    async def health_check(self) -> bool:
        """
        Verify connectivity by querying orders endpoint with limit=1.
        Returns True if reachable and authenticated, False otherwise.
        """
        try:
            await self._request_with_retries("GET", f"{self.orders_path}?count=1")
            return True
        except Exception as exc:
            logger.warning("Razorpay health check failed: %s", exc)
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client if owned by this provider."""
        if not self._external_client:
            await self._client.aclose()
