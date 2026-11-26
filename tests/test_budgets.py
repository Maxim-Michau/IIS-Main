"""Tests for recurring and month-specific budgets."""

from datetime import datetime

from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.insights.insight_engine import InsightEngine
from expense_ai.models.transaction import Transaction
from expense_ai.services.app_service import AppService


def test_default_budget_applies_each_month_and_specific_month_overrides(engine) -> None:
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    service.save_budget("Takeaways", 150.0, "default")
    service.save_budget("Takeaways", 200.0, "2026-02")

    assert service.get_budgets("2026-01") == {"Takeaways": 150.0}
    assert service.get_budgets("2026-02") == {"Takeaways": 200.0}
    assert service.get_budgets("2026-03") == {"Takeaways": 150.0}


def test_recurring_takeaways_budget_warns_in_every_over_budget_month(engine) -> None:
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    service.save_budget("Takeaways", 150.0, "default")
    transactions = [
        Transaction(
            None, datetime(year, month, 20), 1480.0, "DELIVEROO", "Deliveroo",
            "Birmingham", "Takeaways",
        )
        for year, month in ((2026, 1), (2026, 2), (2026, 3))
    ]

    for month in (1, 2, 3):
        warnings = InsightEngine(service.get_budgets(f"2026-{month:02d}")).budget_warnings(
            transactions, 2026, month
        )
        assert warnings
        assert "over the £150.00 budget" in warnings[0]
        assert "£1480.00 spent" in warnings[0]


def test_saved_budget_can_be_edited_and_deleted(engine) -> None:
    """Budget records expose stable IDs for editing and deletion."""
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    service.save_budget("Groceries", 100.0, "2026-03")
    record = service.get_budget_records()[0]

    service.update_budget(int(record["id"]), 0.0)
    assert service.get_budgets("2026-03") == {"Groceries": 0.0}
    assert service.delete_budget(int(record["id"]))
    assert service.get_budget_records() == []
