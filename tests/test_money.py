"""Tests for money conversion utilities."""

import pytest

from orbitalpay_sdk.money import micros_to_usd, usd_to_micros


class TestUsdToMicros:
    def test_zero(self) -> None:
        assert usd_to_micros("0") == 0
        assert usd_to_micros("0.000000") == 0

    def test_one_dollar(self) -> None:
        assert usd_to_micros("1") == 1_000_000
        assert usd_to_micros("1.000000") == 1_000_000

    def test_sub_cent(self) -> None:
        assert usd_to_micros("0.0003") == 300
        assert usd_to_micros("0.000001") == 1

    def test_large_amount(self) -> None:
        assert usd_to_micros("999999.999999") == 999_999_999_999

    def test_whole_cents(self) -> None:
        assert usd_to_micros("0.01") == 10_000
        assert usd_to_micros("49.99") == 49_990_000

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="negative"):
            usd_to_micros("-1.00")

    def test_sub_microdollar_precision_rejected(self) -> None:
        with pytest.raises(ValueError, match="sub-microdollar"):
            usd_to_micros("0.0000001")

    def test_sub_microdollar_precision_rejected_partial(self) -> None:
        with pytest.raises(ValueError, match="sub-microdollar"):
            usd_to_micros("1.0000005")

    def test_invalid_string_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            usd_to_micros("abc")

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            usd_to_micros("")


class TestMicrosToUsd:
    def test_zero(self) -> None:
        assert micros_to_usd(0) == "0.000000"

    def test_one_dollar(self) -> None:
        assert micros_to_usd(1_000_000) == "1.000000"

    def test_one_micro(self) -> None:
        assert micros_to_usd(1) == "0.000001"

    def test_sub_cent(self) -> None:
        assert micros_to_usd(300) == "0.000300"

    def test_large_amount(self) -> None:
        assert micros_to_usd(999_999_999_999) == "999999.999999"

    def test_roundtrip(self) -> None:
        for amount in ["0.000001", "0.000300", "1.000000", "100.500000"]:
            assert micros_to_usd(usd_to_micros(amount)) == amount
