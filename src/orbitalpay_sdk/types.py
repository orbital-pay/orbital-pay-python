"""Dataclasses representing API response objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class WalletInfo:
    """Returned from create_wallet — includes the one-time wallet_secret."""

    id: str
    wallet_secret: str
    label: str
    status: str
    created_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WalletInfo:
        return cls(
            id=data["id"],
            wallet_secret=data["wallet_secret"],
            label=data["label"],
            status=data["status"],
            created_at=data["created_at"],
        )


@dataclass
class WalletResponse:
    """Full wallet details (no secret)."""

    id: str
    owner_id: str
    label: str
    balance_usd: str
    balance_micros: int
    currency: str
    status: str
    daily_limit_micros: int
    spent_today_micros: int
    created_at: str
    updated_at: str
    evm_address: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WalletResponse:
        return cls(
            id=data["id"],
            owner_id=data["owner_id"],
            label=data["label"],
            balance_usd=data["balance_usd"],
            balance_micros=data["balance_micros"],
            currency=data["currency"],
            status=data["status"],
            daily_limit_micros=data["daily_limit_micros"],
            spent_today_micros=data["spent_today_micros"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            evm_address=data.get("evm_address"),
        )


@dataclass
class BalanceInfo:
    """Balance for a wallet."""

    wallet_id: str
    balance_usd: str
    balance_micros: int
    currency: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BalanceInfo:
        return cls(
            wallet_id=data["wallet_id"],
            balance_usd=data["balance_usd"],
            balance_micros=data["balance_micros"],
            currency=data["currency"],
        )


@dataclass
class PaymentReceipt:
    """Receipt from a pay operation."""

    ledger_entry_id: str
    from_wallet_id: str
    to_wallet_id: str
    amount_usd: str
    amount_micros: int
    spread_micros: int
    net_amount_usd: str
    net_amount_micros: int
    idempotency_key: str
    created_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaymentReceipt:
        return cls(
            ledger_entry_id=data["ledger_entry_id"],
            from_wallet_id=data["from_wallet_id"],
            to_wallet_id=data["to_wallet_id"],
            amount_usd=data["amount_usd"],
            amount_micros=data["amount_micros"],
            spread_micros=data["spread_micros"],
            net_amount_usd=data["net_amount_usd"],
            net_amount_micros=data["net_amount_micros"],
            idempotency_key=data["idempotency_key"],
            created_at=data["created_at"],
        )


@dataclass
class LedgerEntry:
    """Single ledger entry."""

    id: str
    entry_type: str
    amount_usd: str
    amount_micros: int
    spread_micros: int
    net_amount_usd: str
    net_amount_micros: int
    currency: str
    created_at: str
    idempotency_key: Optional[str] = None
    from_wallet_id: Optional[str] = None
    to_wallet_id: Optional[str] = None
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LedgerEntry:
        return cls(
            id=data["id"],
            entry_type=data["entry_type"],
            amount_usd=data["amount_usd"],
            amount_micros=data["amount_micros"],
            spread_micros=data["spread_micros"],
            net_amount_usd=data["net_amount_usd"],
            net_amount_micros=data["net_amount_micros"],
            currency=data["currency"],
            created_at=data["created_at"],
            idempotency_key=data.get("idempotency_key"),
            from_wallet_id=data.get("from_wallet_id"),
            to_wallet_id=data.get("to_wallet_id"),
            description=data.get("description"),
        )


@dataclass
class HistoryResponse:
    """Paginated ledger history."""

    items: list[LedgerEntry]
    total: int
    limit: int
    offset: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryResponse:
        return cls(
            items=[LedgerEntry.from_dict(item) for item in data["items"]],
            total=data["total"],
            limit=data["limit"],
            offset=data["offset"],
        )


@dataclass
class ReputationInfo:
    """Reputation data for a wallet."""

    wallet_id: str
    score: float
    tier: str
    total_payments: int
    success_rate: float
    unique_counterparties: int
    age_days: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReputationInfo:
        return cls(
            wallet_id=data["wallet_id"],
            score=data["score"],
            tier=data["tier"],
            total_payments=data["total_payments"],
            success_rate=data["success_rate"],
            unique_counterparties=data["unique_counterparties"],
            age_days=data["age_days"],
        )


@dataclass
class PermitResponse:
    """Permit returned from auth endpoint."""

    permit: str
    expires_at: str
    scope: str
    max_uses: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PermitResponse:
        return cls(
            permit=data["permit"],
            expires_at=data["expires_at"],
            scope=data["scope"],
            max_uses=data["max_uses"],
        )


