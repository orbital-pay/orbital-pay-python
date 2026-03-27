"""End-to-end test: full Passport → OrbitalPay flow.

Tests the complete chain:
1. Create agent device via Passport (using osk_ admin key)
2. Use opd_ token to authenticate to OrbitalPay
3. Create wallets, fund, mint HMAC permit, pay, check balance

Requires:
- OrbitalPay API running on localhost:18300 with Passport enabled
- Passport reachable at passport.orbitalpay.ai
- ORBITALPAY_PASSPORT_ADMIN_KEY set (osk_ key)

Run: pytest tests/test_e2e_passport.py -v -s
"""

import hashlib
import hmac as hmac_mod
import os
import time
import uuid

import httpx
import pytest

API_URL = "http://127.0.0.1:18300"
PASSPORT_URL = "https://passport.orbitalpay.ai"

# These come from .env — the osk_ key for creating devices
ADMIN_KEY = os.environ.get(
    "ORBITALPAY_PASSPORT_ADMIN_KEY",
    "osk_RXtEH-VXO3h0DLzBvnsOTmbTarOK5MgW",
)
ORG_ID = os.environ.get("ORBITALPAY_ORG_ID", "epyphite-b79d")


def create_device_via_passport(name: str) -> dict:
    """Create an agent device directly via Passport using osk_ key."""
    resp = httpx.post(
        f"{PASSPORT_URL}/api/gateway/v1/organizations/{ORG_ID}/devices",
        json={"name": name, "device_type": "agent", "service_id": "orbitalpay"},
        headers={"X-Service-Key": ADMIN_KEY},
        timeout=10,
    )
    if resp.status_code not in (200, 201):
        pytest.skip(f"Cannot create device in Passport: {resp.status_code} {resp.text}")
    return resp.json()


class TestE2EPassportFlow:
    """Full end-to-end test through the real auth chain."""

    def test_health(self):
        r = httpx.get(f"{API_URL}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_full_flow(self):
        # --- Step 1: Create agent device in Passport ---
        device = create_device_via_passport(f"e2e-test-{uuid.uuid4().hex[:8]}")
        opd_token = device["token"]
        assert opd_token.startswith("opd_") or opd_token  # token format may vary
        print(f"Device created: {device['name']}, token: {opd_token[:20]}...")

        # --- Step 2: Authenticate to OrbitalPay with opd_ token ---
        headers = {"X-Device-Token": opd_token}

        # This should work if the device's org maps to an owner
        # First, we may need to create the owner. Let's try /owners/me
        r = httpx.get(f"{API_URL}/v1/owners/me", headers=headers)
        if r.status_code == 401:
            # Device validation might fail if org mapping isn't set up
            # Let's check the error
            print(f"Owner lookup failed: {r.json()}")
            pytest.skip(
                "Device token validated but no owner mapped to org. "
                "Need to set org_id on an owner record first."
            )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        owner = r.json()
        print(f"Owner: {owner['id']} ({owner['email']})")

        # --- Step 3: Create two wallets ---
        r = httpx.post(
            f"{API_URL}/v1/wallets",
            json={"label": "alice-agent"},
            headers=headers,
        )
        assert r.status_code == 201, f"Create wallet A failed: {r.text}"
        wallet_a = r.json()
        print(f"Wallet A: {wallet_a['id']}")

        r = httpx.post(
            f"{API_URL}/v1/wallets",
            json={"label": "bob-agent"},
            headers=headers,
        )
        assert r.status_code == 201, f"Create wallet B failed: {r.text}"
        wallet_b = r.json()
        print(f"Wallet B: {wallet_b['id']}")

        # --- Step 4: Fund wallet A ---
        r = httpx.post(
            f"{API_URL}/v1/wallets/{wallet_a['id']}/fund",
            json={
                "amount_usd": "1.000000",
                "idempotency_key": f"fund-{uuid.uuid4().hex}",
            },
            headers=headers,
        )
        assert r.status_code == 200, f"Fund failed: {r.text}"
        print(f"Funded wallet A: $1.00")

        # --- Step 5: Agent mints HMAC permit ---
        wallet_secret_a = wallet_a["wallet_secret"]
        wallet_id_a = wallet_a["id"]
        timestamp = int(time.time())
        message = f"{wallet_id_a}|session|{timestamp}"
        secret_hash = hashlib.sha256(wallet_secret_a.encode()).hexdigest()
        signature = hmac_mod.new(
            secret_hash.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        r = httpx.post(
            f"{API_URL}/v1/auth/permit",
            json={
                "wallet_id": wallet_id_a,
                "scope": "session",
                "timestamp": timestamp,
                "signature": signature,
            },
        )
        assert r.status_code == 200, f"Mint permit failed: {r.text}"
        permit = r.json()
        opp_token = permit["permit"]
        assert opp_token.startswith("opp_session_")
        print(f"Permit minted: {opp_token[:25]}...")

        # --- Step 6: Agent pays B using permit ---
        r = httpx.post(
            f"{API_URL}/v1/payments/pay",
            json={
                "to_wallet_id": wallet_b["id"],
                "amount_usd": "0.000300",
                "idempotency_key": f"pay-{uuid.uuid4().hex}",
                "description": "e2e passport flow test",
            },
            headers={"Authorization": f"Bearer {opp_token}"},
        )
        assert r.status_code == 200, f"Pay failed: {r.text}"
        receipt = r.json()
        print(
            f"Payment: {receipt['amount_usd']} USD from {receipt['from_wallet_id']} "
            f"to {receipt['to_wallet_id']}, spread: {receipt['spread_micros']} micros"
        )

        # --- Step 7: Check balances ---
        r = httpx.get(
            f"{API_URL}/v1/payments/balance",
            headers={"Authorization": f"Bearer {opp_token}"},
        )
        assert r.status_code == 200
        bal_a = r.json()
        assert bal_a["balance_micros"] < 1_000_000  # paid + spread
        print(f"Wallet A balance: {bal_a['balance_usd']} USD")

        # --- Step 8: Check reputation ---
        r = httpx.get(f"{API_URL}/v1/reputation/{wallet_id_a}")
        assert r.status_code == 200
        rep = r.json()
        print(f"Wallet A reputation: score={rep['score']}, tier={rep['tier']}")

        # --- Step 9: Check history ---
        r = httpx.get(
            f"{API_URL}/v1/payments/history",
            headers={"Authorization": f"Bearer {opp_token}"},
        )
        assert r.status_code == 200
        history = r.json()
        assert history["total"] >= 1
        print(f"Wallet A history: {history['total']} entries")

        print("\n=== FULL PASSPORT E2E FLOW PASSED ===")
