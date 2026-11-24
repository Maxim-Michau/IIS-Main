"""Tests for categorisation pipeline."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.pipeline import CategorisationPipeline


def make_transaction(merchant: str) -> Transaction:
    """Create a simple test transaction."""
    return Transaction(None, datetime.now(), 10.0, merchant, merchant, "Birmingham")


def test_rule_categoriser() -> None:
    """Known merchants receive rule predictions."""
    prediction = RuleCategoriser().categorise(make_transaction("TESCO STORES 4521"))
    assert prediction.category == "Groceries"
    assert prediction.confidence_score >= 0.85


def test_pipeline_stops_on_rule() -> None:
    """High-confidence rule matches end the cascade."""
    pipeline = CategorisationPipeline([RuleCategoriser()])
    prediction = pipeline.categorise(make_transaction("NETFLIX.COM"))
    assert prediction.category == "Subscriptions"
