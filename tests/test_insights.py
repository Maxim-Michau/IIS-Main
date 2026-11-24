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


def test_anomaly_subscription_and_month_trend() -> None:
    """Anomalies and repeat subscriptions are derived from stored transactions."""
    transactions = []
    for month in range(1, 5):
        for week in range(4):
            amount = 200.0 if month == 4 and week == 3 else 10.0
            transactions.append(Transaction(
                None, datetime(2026, month, week * 7 + 1), amount,
                "NETFLIX", "Netflix", "Birmingham", "Subscriptions"
            ))
    engine = InsightEngine({"Subscriptions": 100.0})
    assert engine.category_anomalies(transactions)
    assert "Netflix" in engine.subscription_suggestions(transactions)
