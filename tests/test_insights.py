"""Tests for insight calculations."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.insights.insight_engine import InsightEngine


def test_budget_warning() -> None:
    """A 80 percent or 100 percent budget threshold creates a warning."""
    transactions = [Transaction(None, datetime(2026, 1, 5), 85.0,
                               "Tesco", "Tesco", "Birmingham", "Groceries")]
    warnings = InsightEngine({"Groceries": 100.0}).budget_warnings(
        transactions, 2026, 1
    )
    assert warnings
    assert "80%" in warnings[0]
