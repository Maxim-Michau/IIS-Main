"""Tests for bank data sources."""

from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.sources.open_banking import OpenBankingSource


def test_synthetic_source_is_reproducible() -> None:
    """Six-month sample data is seeded and complete."""
    first = list(SyntheticBankSource(seed=42).fetch_transactions())
    second = list(SyntheticBankSource(seed=42).fetch_transactions())
    assert len(first) > 300
    assert [(row.merchant_raw, row.amount) for row in first] == [
        (row.merchant_raw, row.amount) for row in second
    ]
    assert any(row.true_category == "Rent & Bills" for row in first)


def test_open_banking_is_not_implemented() -> None:
    """Real bank access is deliberately disabled."""
    try:
        OpenBankingSource().fetch_transactions()
        assert False
    except NotImplementedError:
        assert True
