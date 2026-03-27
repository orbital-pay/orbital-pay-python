"""Money conversion utilities. No floats allowed."""

from decimal import Decimal, InvalidOperation

MICROS_PER_USD = 1_000_000

_MICROS_DECIMAL = Decimal(MICROS_PER_USD)
_SCALE = Decimal("0.000001")


def usd_to_micros(amount: str) -> int:
    """Convert a USD decimal string to microdollars (int).

    Raises ValueError on negative amounts, sub-microdollar precision,
    or unparseable input.
    """
    try:
        d = Decimal(amount)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"invalid USD amount: {amount!r}") from exc

    if d < 0:
        raise ValueError(f"negative amount not allowed: {amount}")

    micros = d * _MICROS_DECIMAL
    if micros != micros.to_integral_value():
        raise ValueError(f"sub-microdollar precision not allowed: {amount}")

    return int(micros)


def micros_to_usd(micros: int) -> str:
    """Convert microdollars (int) to a USD decimal string with 6 decimal places."""
    d = Decimal(micros) / _MICROS_DECIMAL
    return str(d.quantize(_SCALE))
