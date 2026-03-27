"""End-to-end test against running API + Passport.

Run: pytest tests/test_e2e.py -v -s
Requires: API running on localhost:18300 and Passport running for opd_ token creation.

# E2E tests require Passport to be running for opd_ token creation.
# The old approach of bootstrapping an opk_ API key via direct SQLite insert
# no longer applies. Device tokens (opd_) are issued by Passport and cannot
# be minted locally.
"""

import os

import httpx
import pytest

BASE_URL = "http://127.0.0.1:18300"


pytestmark = pytest.mark.skip(
    reason="E2E tests require Passport to be running for opd_ token creation"
)


class TestE2EHealth:
    def test_api_reachable(self):
        r = httpx.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


class TestE2EFullFlow:
    """Register owner, create wallets, fund, pay, check balance and reputation.

    To run these tests, set ORBITALPAY_DEVICE_TOKEN to a valid opd_ token
    obtained from Passport, then remove the module-level skip marker.
    """

    @pytest.fixture(scope="module")
    def client(self):
        from orbitalpay_sdk import OrbitalPay

        token = os.environ.get("ORBITALPAY_DEVICE_TOKEN")
        if not token:
            pytest.skip("ORBITALPAY_DEVICE_TOKEN not set")
        return OrbitalPay(BASE_URL, device_token=token)

    def test_full_payment_flow(self, client):
        from orbitalpay_sdk import OrbitalPayError

        # Create wallet A
        wallet_a = client.create_wallet("agent-alice")
        assert wallet_a.id.startswith("opw_")
        assert wallet_a.wallet_secret  # shown once
        print(f"Wallet A: {wallet_a.id}")

        # Create wallet B
        wallet_b = client.create_wallet("agent-bob")
        assert wallet_b.id.startswith("opw_")
        print(f"Wallet B: {wallet_b.id}")

        # List wallets — should include both
        wallets = client.list_wallets()
        wallet_ids = [w.id for w in wallets]
        assert wallet_a.id in wallet_ids
        assert wallet_b.id in wallet_ids

        # Get wallet A
        wa = client.get_wallet(wallet_a.id)
        assert wa.balance_micros == 0
        assert wa.status == "active"

        # Fund wallet A with $1.00
        fund_result = client.fund_wallet(wallet_a.id, "1.000000")
        print(f"Fund result: {fund_result}")

        # Verify balance after funding
        wa = client.get_wallet(wallet_a.id)
        assert wa.balance_micros == 1_000_000
        print(f"Wallet A balance after fund: {wa.balance_usd}")

        # Create agent handles
        handle_a = client.wallet(wallet_a.id, wallet_a.wallet_secret)

        # Check balance via agent handle
        bal = handle_a.balance()
        assert bal.balance_micros == 1_000_000
        assert bal.balance_usd == "1.000000"
        print(f"Agent A balance: {bal.balance_usd} USD")

        # Pay $0.0003 from A to B
        receipt = handle_a.pay(wallet_b.id, "0.000300", "e2e test payment")
        assert receipt.from_wallet_id == wallet_a.id
        assert receipt.to_wallet_id == wallet_b.id
        assert receipt.amount_micros == 300
        print(f"Payment receipt: {receipt.amount_usd} USD, spread: {receipt.spread_micros} micros")

        # Check balances after payment
        bal_a = handle_a.balance()
        assert bal_a.balance_micros < 1_000_000  # paid + spread
        print(f"Agent A after pay: {bal_a.balance_usd} USD")

        handle_b = client.wallet(wallet_b.id, wallet_b.wallet_secret)
        bal_b = handle_b.balance()
        assert bal_b.balance_micros > 0  # received net amount
        print(f"Agent B after pay: {bal_b.balance_usd} USD")

        # Check history
        history = handle_a.history(limit=10)
        assert history.total >= 1
        print(f"Agent A history: {history.total} entries")

        # Check reputation (public endpoint)
        rep = handle_a.reputation(wallet_a.id)
        assert rep.wallet_id == wallet_a.id
        assert rep.tier  # should have a tier
        print(f"Agent A reputation: score={rep.score}, tier={rep.tier}")

        # Freeze wallet A
        client.freeze_wallet(wallet_a.id)
        wa = client.get_wallet(wallet_a.id)
        assert wa.status == "frozen"
        print("Wallet A frozen")

        # Unfreeze wallet A
        client.unfreeze_wallet(wallet_a.id)
        wa = client.get_wallet(wallet_a.id)
        assert wa.status == "active"
        print("Wallet A unfrozen")

        print("\n=== E2E FULL FLOW PASSED ===")
