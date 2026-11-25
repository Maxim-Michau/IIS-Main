"""Tests for bank data sources."""

from datetime import date

from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.sources.open_banking import OpenBankingSource


def test_synthetic_source_is_reproducible() -> None:
    """Six-month sample data is seeded and complete."""
    fixed_end = date(2026, 6, 30)
    first = list(SyntheticBankSource(seed=42, end_date=fixed_end).fetch_transactions())
    second = list(SyntheticBankSource(seed=42, end_date=fixed_end).fetch_transactions())
    assert len(first) > 300
    assert [(row.merchant_raw, row.amount) for row in first] == [
        (row.merchant_raw, row.amount) for row in second
    ]
    assert any(row.true_category == "Rent & Bills" for row in first)
    assert min(row.timestamp.date() for row in first) == date(2026, 1, 1)
    assert max(row.timestamp.date() for row in first) == fixed_end


def test_synthetic_source_defaults_to_today() -> None:
    """The generated window ends on today's date unless a fixed date is supplied."""
    transactions = list(SyntheticBankSource(seed=42).fetch_transactions())
    assert max(item.timestamp.date() for item in transactions) == date.today()


def test_open_banking_is_not_implemented() -> None:
    """Real bank access is deliberately disabled."""
    try:
        OpenBankingSource().fetch_transactions()
        assert False
    except NotImplementedError:
        assert True
