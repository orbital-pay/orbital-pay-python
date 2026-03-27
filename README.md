# orbitalpay-sdk

Python SDK for the OrbitalPay agent micropayment service.

## Installation

```bash
pip install orbitalpay-sdk
```

> **Warning**: The `wallet_secret` is shown once at wallet creation. Save it immediately. If lost, use `POST /v1/wallets/{id}/rotate-secret` (owner auth required) to generate a new one.

## Quickstart

```python
from orbitalpay_sdk import OrbitalPay

# Owner client — manage wallets with your Passport device token
client = OrbitalPay("http://localhost:18300", device_token="opd_your_token")
wallet = client.create_wallet("my-agent")

# Agent handle — make payments with wallet credentials
handle = client.wallet(wallet.id, wallet.wallet_secret)
receipt = handle.pay("opw_recipient", "0.0003", "test payment")
print(handle.balance())
```

## Owner Operations

```python
client = OrbitalPay(base_url, device_token="opd_...")

# Wallets
wallet = client.create_wallet("label", daily_limit_micros=5_000_000)
wallets = client.list_wallets()
info = client.get_wallet("opw_...")
client.fund_wallet("opw_...", "10.00")
client.drain_wallet("opw_...")
client.freeze_wallet("opw_...")
client.unfreeze_wallet("opw_...")
```

## Agent Operations

```python
handle = client.wallet("opw_...", "wallet_secret")

receipt = handle.pay("opw_recipient", "0.0003", description="data purchase")
balance = handle.balance()
history = handle.history(limit=20, offset=0)
rep = handle.reputation()            # own reputation
rep = handle.reputation("opw_other") # another wallet's reputation
```

## Error Handling

All exceptions inherit from `OrbitalPayError`:

| Exception | Meaning |
|-----------|---------|
| `OrbitalPayError` | Base class for all SDK errors |
| `AuthenticationError` | Invalid or expired device token / wallet secret (HTTP 401) |
| `ForbiddenError` | Permission denied, e.g. frozen wallet (HTTP 403) |
| `NotFoundError` | Wallet or resource not found (HTTP 404) |
| `InsufficientFundsError` | Balance too low for the requested payment (HTTP 409) |
| `RateLimitError` | Velocity limit or rate limit exceeded (HTTP 429) |
| `ServerError` | OrbitalPay API returned 5xx |

```python
from orbitalpay_sdk import OrbitalPay, OrbitalPayError, InsufficientFundsError

try:
    handle.pay("opw_target", "1.00")
except InsufficientFundsError:
    print("Not enough balance")
except OrbitalPayError as e:
    print(e.status_code, e.message, e.detail)
```

## Sync-Only

This SDK is synchronous (`httpx.Client`). For async, use `httpx.AsyncClient` directly with the same API endpoints and HMAC signing logic.

## See Also

- [Integration Guide](../docs/integration-guide.md) — Full setup guide for all integration paths
- [Architecture](../docs/architecture.md) — System design, auth model, database schema
- [SDK Reference](../docs/sdk.md) — Full SDK documentation with all types and examples
- **Other tools**: [API](../orbitalpay-api/) | [SDK](../orbitalpay-sdk/) | [MCP](../orbitalpay-mcp/) | [CLI](../orbitalpay-cli/) | [x402](../orbitalpay-x402/) | [Dashboard](../orbitalpay-dashboard/)
