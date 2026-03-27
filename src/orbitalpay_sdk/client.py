"""OrbitalPay SDK client classes."""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .exceptions import raise_for_status
from .types import (
    BalanceInfo,
    HistoryResponse,
    PaymentReceipt,
    PermitResponse,
    ReputationInfo,
    WalletInfo,
    WalletResponse,
)


class OrbitalPay:
    """Owner-level client for the OrbitalPay API.

    Uses ``X-Device-Token`` authentication (Passport device tokens) for
    wallet management operations.
    """

    def __init__(self, base_url: str, device_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.device_token = device_token
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-Device-Token": self.device_token},
            timeout=30.0,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> OrbitalPay:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- Wallet operations --

    def create_wallet(
        self,
        label: str,
        daily_limit_micros: Optional[int] = None,
    ) -> WalletInfo:
        """Create a new agent wallet."""
        body: dict[str, Any] = {"label": label}
        if daily_limit_micros is not None:
            body["daily_limit_micros"] = daily_limit_micros
        resp = self._client.post("/v1/wallets", json=body)
        raise_for_status(resp)
        return WalletInfo.from_dict(resp.json())

    def list_wallets(self) -> list[WalletResponse]:
        """List all wallets owned by the authenticated owner."""
        resp = self._client.get("/v1/wallets")
        raise_for_status(resp)
        data = resp.json()
        items = data if isinstance(data, list) else data.get("wallets", data.get("items", []))
        return [WalletResponse.from_dict(w) for w in items]

    def get_wallet(self, wallet_id: str) -> WalletResponse:
        """Get details for a specific wallet."""
        resp = self._client.get(f"/v1/wallets/{wallet_id}")
        raise_for_status(resp)
        return WalletResponse.from_dict(resp.json())

    def fund_wallet(
        self,
        wallet_id: str,
        amount_usd: str,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Add funds to a wallet."""
        body: dict[str, Any] = {
            "amount_usd": amount_usd,
            "idempotency_key": idempotency_key or str(uuid.uuid4()),
        }
        resp = self._client.post(f"/v1/wallets/{wallet_id}/fund", json=body)
        raise_for_status(resp)
        return resp.json()

    def drain_wallet(self, wallet_id: str) -> dict[str, Any]:
        """Drain all funds from a wallet."""
        resp = self._client.post(f"/v1/wallets/{wallet_id}/drain")
        raise_for_status(resp)
        return resp.json()

    def freeze_wallet(self, wallet_id: str) -> dict[str, Any]:
        """Freeze a wallet, preventing transactions."""
        resp = self._client.post(f"/v1/wallets/{wallet_id}/freeze")
        raise_for_status(resp)
        return resp.json()

    def unfreeze_wallet(self, wallet_id: str) -> dict[str, Any]:
        """Unfreeze a previously frozen wallet."""
        resp = self._client.post(f"/v1/wallets/{wallet_id}/unfreeze")
        raise_for_status(resp)
        return resp.json()

    # -- Factory --

    def wallet(self, wallet_id: str, wallet_secret: str) -> WalletHandle:
        """Create a WalletHandle for agent-level operations."""
        return WalletHandle(self.base_url, wallet_id, wallet_secret)


class WalletHandle:
    """Agent-level client bound to a single wallet.

    Automatically mints and caches session permits via HMAC-SHA256.
    """

    def __init__(self, base_url: str, wallet_id: str, wallet_secret: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.wallet_id = wallet_id
        self.wallet_secret = wallet_secret
        self._client = httpx.Client(base_url=self.base_url, timeout=30.0)
        self._permit: Optional[PermitResponse] = None

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> WalletHandle:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- Public API --

    def pay(
        self,
        to_wallet_id: str,
        amount_usd: str,
        description: str = "",
        idempotency_key: Optional[str] = None,
    ) -> PaymentReceipt:
        """Send a payment to another wallet."""
        body: dict[str, Any] = {
            "to_wallet_id": to_wallet_id,
            "amount_usd": amount_usd,
            "idempotency_key": idempotency_key or str(uuid.uuid4()),
            "description": description,
        }
        data = self._authed_request("POST", "/v1/payments/pay", json=body)
        return PaymentReceipt.from_dict(data)

    def balance(self) -> BalanceInfo:
        """Get the current balance for this wallet."""
        data = self._authed_request("GET", "/v1/payments/balance")
        return BalanceInfo.from_dict(data)

    def history(self, limit: int = 50, offset: int = 0) -> HistoryResponse:
        """Get payment history for this wallet."""
        data = self._authed_request(
            "GET",
            "/v1/payments/history",
            params={"limit": limit, "offset": offset},
        )
        return HistoryResponse.from_dict(data)

    def reputation(self, wallet_id: Optional[str] = None) -> ReputationInfo:
        """Get reputation info for a wallet (defaults to own)."""
        target = wallet_id or self.wallet_id
        data = self._authed_request("GET", f"/v1/reputation/{target}")
        return ReputationInfo.from_dict(data)

    # -- Internals --

    def _mint_permit(self, scope: str) -> PermitResponse:
        """Mint a permit by signing a message with HMAC-SHA256.

        The server verifies using wallet_secret_hash = SHA256(wallet_secret).
        So we must hash our raw secret before using it as the HMAC key.
        """
        timestamp = int(time.time())
        message = f"{self.wallet_id}|{scope}|{timestamp}"
        # Server uses wallet_secret_hash as HMAC key, so we must too
        secret_hash = hashlib.sha256(self.wallet_secret.encode()).hexdigest()
        signature = hmac.new(
            secret_hash.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        resp = self._client.post(
            "/v1/auth/permit",
            json={
                "wallet_id": self.wallet_id,
                "scope": scope,
                "timestamp": timestamp,
                "signature": signature,
            },
        )
        raise_for_status(resp)
        return PermitResponse.from_dict(resp.json())

    def _ensure_permit(self) -> str:
        """Return a valid session permit token, minting one if needed."""
        if self._permit is not None:
            expires = datetime.fromisoformat(self._permit.expires_at.replace("Z", "+00:00"))
            if expires > datetime.now(timezone.utc):
                return self._permit.permit
        self._permit = self._mint_permit("session")
        return self._permit.permit

    def _authed_request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an authenticated request using the cached session permit."""
        token = self._ensure_permit()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        resp = self._client.request(method, path, headers=headers, **kwargs)
        raise_for_status(resp)
        return resp.json()
