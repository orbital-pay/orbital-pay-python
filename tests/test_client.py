"""Tests for OrbitalPay and WalletHandle clients."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from orbitalpay_sdk import (
    AuthenticationError,
    NotFoundError,
    OrbitalPay,
    ServerError,
    WalletHandle,
)

BASE_URL = "http://localhost:18300"
DEVICE_TOKEN = "opd_test_device_token"
WALLET_ID = "opw_test_wallet"
WALLET_SECRET = "secret_abc123"


@pytest.fixture
def client() -> OrbitalPay:
    c = OrbitalPay(BASE_URL, device_token=DEVICE_TOKEN)
    yield c
    c.close()


def _wallet_created_response() -> dict[str, Any]:
    return {
        "id": WALLET_ID,
        "wallet_secret": WALLET_SECRET,
        "label": "test-agent",
        "status": "active",
        "created_at": "2026-03-18T00:00:00Z",
    }


def _wallet_response() -> dict[str, Any]:
    return {
        "id": WALLET_ID,
        "owner_id": "own_123",
        "label": "test-agent",
        "balance_usd": "10.000000",
        "balance_micros": 10_000_000,
        "currency": "USD",
        "status": "active",
        "daily_limit_micros": 5_000_000,
        "spent_today_micros": 0,
        "evm_address": None,
        "created_at": "2026-03-18T00:00:00Z",
        "updated_at": "2026-03-18T00:00:00Z",
    }


def _permit_response() -> dict[str, Any]:
    return {
        "permit": "opp_session_token",
        "expires_at": "2099-12-31T23:59:59Z",
        "scope": "session",
        "max_uses": 0,
    }


def _balance_response() -> dict[str, Any]:
    return {
        "wallet_id": WALLET_ID,
        "balance_usd": "10.000000",
        "balance_micros": 10_000_000,
        "currency": "USD",
    }


def _payment_receipt_response() -> dict[str, Any]:
    return {
        "ledger_entry_id": "txn_001",
        "from_wallet_id": WALLET_ID,
        "to_wallet_id": "opw_recipient",
        "amount_usd": "0.000300",
        "amount_micros": 300,
        "spread_micros": 0,
        "net_amount_usd": "0.000300",
        "net_amount_micros": 300,
        "idempotency_key": "idem_001",
        "created_at": "2026-03-18T00:00:00Z",
    }


class TestOrbitalPay:
    def test_create_wallet(self, client: OrbitalPay, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/wallets",
            method="POST",
            json=_wallet_created_response(),
            status_code=201,
        )
        wallet = client.create_wallet("test-agent", daily_limit_micros=5_000_000)
        assert wallet.id == WALLET_ID
        assert wallet.wallet_secret == WALLET_SECRET
        assert wallet.label == "test-agent"

    def test_list_wallets(self, client: OrbitalPay, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/wallets",
            method="GET",
            json=[_wallet_response()],
        )
        wallets = client.list_wallets()
        assert len(wallets) == 1
        assert wallets[0].id == WALLET_ID

    def test_get_wallet(self, client: OrbitalPay, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/wallets/{WALLET_ID}",
            method="GET",
            json=_wallet_response(),
        )
        w = client.get_wallet(WALLET_ID)
        assert w.balance_usd == "10.000000"

    def test_fund_wallet(self, client: OrbitalPay, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/wallets/{WALLET_ID}/fund",
            method="POST",
            json={"status": "ok"},
        )
        result = client.fund_wallet(WALLET_ID, "5.00")
        assert result["status"] == "ok"

    def test_device_token_header_sent(self, client: OrbitalPay, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/wallets",
            method="GET",
            json=[],
        )
        client.list_wallets()
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["X-Device-Token"] == DEVICE_TOKEN

    def test_wallet_factory(self, client: OrbitalPay) -> None:
        handle = client.wallet(WALLET_ID, WALLET_SECRET)
        assert isinstance(handle, WalletHandle)
        assert handle.wallet_id == WALLET_ID
        handle.close()


class TestWalletHandle:
    def test_pay_mints_permit_and_sends(self, httpx_mock: HTTPXMock) -> None:
        # First call: mint session permit
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/auth/permit",
            method="POST",
            json=_permit_response(),
        )
        # Second call: actual payment
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/payments/pay",
            method="POST",
            json=_payment_receipt_response(),
        )

        with WalletHandle(BASE_URL, WALLET_ID, WALLET_SECRET) as handle:
            receipt = handle.pay("opw_recipient", "0.0003", "test payment", "idem_001")

        assert receipt.ledger_entry_id == "txn_001"
        assert receipt.amount_usd == "0.000300"

        # Verify permit request has correct HMAC structure
        permit_req = httpx_mock.get_requests()[0]
        body = json.loads(permit_req.content)
        assert body["wallet_id"] == WALLET_ID
        assert body["scope"] == "session"

        # Verify HMAC signature (SDK hashes the secret before using as HMAC key)
        message = f"{WALLET_ID}|{body['scope']}|{body['timestamp']}"
        secret_hash = hashlib.sha256(WALLET_SECRET.encode()).hexdigest()
        expected_sig = hmac.new(
            secret_hash.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        assert body["signature"] == expected_sig

        # Verify payment request uses Bearer token
        pay_req = httpx_mock.get_requests()[1]
        assert pay_req.headers["Authorization"] == "Bearer opp_session_token"

    def test_balance(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/auth/permit",
            method="POST",
            json=_permit_response(),
        )
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/payments/balance",
            method="GET",
            json=_balance_response(),
        )

        with WalletHandle(BASE_URL, WALLET_ID, WALLET_SECRET) as handle:
            bal = handle.balance()

        assert bal.wallet_id == WALLET_ID
        assert bal.balance_micros == 10_000_000

    def test_permit_cached_on_second_call(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/auth/permit",
            method="POST",
            json=_permit_response(),
        )
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/payments/balance",
            method="GET",
            json=_balance_response(),
        )
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/payments/balance",
            method="GET",
            json=_balance_response(),
        )

        with WalletHandle(BASE_URL, WALLET_ID, WALLET_SECRET) as handle:
            handle.balance()
            handle.balance()

        # Only one permit request should have been made
        permit_requests = [
            r for r in httpx_mock.get_requests() if "/v1/auth/permit" in str(r.url)
        ]
        assert len(permit_requests) == 1


class TestErrorHandling:
    def test_401_raises_authentication_error(
        self, client: OrbitalPay, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/wallets",
            method="GET",
            json={"message": "invalid api key"},
            status_code=401,
        )
        with pytest.raises(AuthenticationError) as exc_info:
            client.list_wallets()
        assert exc_info.value.status_code == 401

    def test_404_raises_not_found_error(
        self, client: OrbitalPay, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/wallets/{WALLET_ID}",
            method="GET",
            json={"message": "wallet not found"},
            status_code=404,
        )
        with pytest.raises(NotFoundError) as exc_info:
            client.get_wallet(WALLET_ID)
        assert exc_info.value.status_code == 404

    def test_500_raises_server_error(
        self, client: OrbitalPay, httpx_mock: HTTPXMock
    ) -> None:
        httpx_mock.add_response(
            url=f"{BASE_URL}/v1/wallets",
            method="GET",
            json={"message": "internal error"},
            status_code=500,
        )
        with pytest.raises(ServerError):
            client.list_wallets()
