"""Tests for insight calculations."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.insights.insight_engine import InsightEngine
from expense_ai.storage.database import insights_table
from sqlalchemy import select
from sqlalchemy.orm import Session


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


def test_takeaways_budget_below_actual_spend() -> None:
    """A £150 Takeaways budget warns when actual monthly spend exceeds it."""
    transactions = [
        Transaction(None, datetime(2026, 11, 5), 90.0,
                    "DELIVEROO", "Deliveroo", "Birmingham", "Takeaways"),
        Transaction(None, datetime(2026, 11, 12), 80.0,
                    "UBER EATS", "Uber Eats", "Birmingham", "Takeaways"),
    ]
    warnings = InsightEngine({"Takeaways": 150.0}).budget_warnings(
        transactions, 2026, 11
    )
    assert warnings
    assert "£170.00" in warnings[0]


def test_savings_suggestion_uses_observed_months_and_order_value() -> None:
    """Takeaway savings use the actual observed month and order counts."""
    transactions = [
        Transaction(None, datetime(2026, 10, 5), 20.0, "A", "A", None, "Takeaways"),
        Transaction(None, datetime(2026, 10, 12), 40.0, "B", "B", None, "Takeaways"),
        Transaction(None, datetime(2026, 11, 5), 30.0, "A", "A", None, "Takeaways"),
    ]

    suggestion = InsightEngine().savings_suggestions(transactions)[0]

    assert suggestion["estimated_monthly_saving"] == 240.0
    assert "£45.00 per observed month across 2 months" in suggestion["explanation"]
    assert "£30.00 across 3 orders" in suggestion["explanation"]
    assert "8 orders" in suggestion["explanation"]


def test_trend_uses_complete_months_and_labels_partial_month() -> None:
    """A partial current month is excluded from takeaway trend calculations."""
    transactions = [
        Transaction(None, datetime(2026, 9, 5), 100.0, "A", "A", None, "Takeaways"),
        Transaction(None, datetime(2026, 10, 5), 150.0, "A", "A", None, "Takeaways"),
        Transaction(None, datetime(2026, 11, 5), 900.0, "A", "A", None, "Takeaways"),
    ]

    trend = InsightEngine(now=datetime(2026, 11, 15)).takeaway_trend(transactions)

    assert "2026-09 to 2026-10" in trend
    assert "November 2026 is partial and excluded" in trend


def test_insight_storage_deduplicates_titles_and_updates_savings(engine) -> None:
    """A title maps to one persisted insight row and keeps its status."""
    insights = InsightEngine(engine=engine)
    first_id = insights.store_actions("Save", "First", 12.0)
    second_id = insights.store_actions("Save", "Updated", 24.0)
    insights.set_action_status(first_id, "DISMISSED")
    insights.store_actions("Save", "Latest", 36.0)

    with Session(engine) as session:
        rows = session.execute(select(insights_table)).mappings().all()

    assert second_id == first_id
    assert len(rows) == 1
    assert rows[0]["explanation"] == "Latest"
    assert rows[0]["estimated_monthly_saving"] == 36.0
    assert rows[0]["status"] == "DISMISSED"


def test_zero_budget_warns_only_when_spending_is_positive() -> None:
    """A zero limit is meaningful without creating a false warning at zero spend."""
    transactions = [
        Transaction(None, datetime(2026, 1, 5), 5.0, "A", "A", None, "Groceries")
    ]

    warnings = InsightEngine({"Groceries": 0.0}).budget_warnings(
        transactions, 2026, 1
    )

    assert warnings == ["Groceries: £5.00 spent against a £0.00 budget."]
