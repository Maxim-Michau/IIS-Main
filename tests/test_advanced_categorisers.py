"""Tests for context-based and fuzzy categorisation methods."""

from datetime import datetime

from expense_ai.ai.categorisers.base import Categoriser
from expense_ai.ai.categorisers.context import ContextCategoriser
from expense_ai.ai.categorisers.fuzzy import FuzzyMerchantCategoriser
from expense_ai.ai.categorisers.recurrence import RecurrenceDetector
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.storage.repository import TransactionRepository


def make_transaction(
    merchant: str = "Unknown Merchant",
    timestamp: datetime | None = None,
    amount: float = 25.0,
    **kwargs: object,
) -> Transaction:
    return Transaction(
        None, timestamp or datetime(2026, 11, 25, 12), amount,
        merchant, merchant, "Birmingham", **kwargs,
    )


def test_fuzzy_categoriser_uses_confirmed_merchant_history(engine) -> None:
    repository = TransactionRepository(engine)
    repository.add(make_transaction(
        "Fresh Market", category="Groceries", status="CONFIRMED"
    ))
    categoriser = FuzzyMerchantCategoriser(engine)

    prediction = categoriser.categorise(make_transaction("Fresh Market 12"))

    assert prediction.category == "Groceries"
    assert prediction.method == "FUZZY"
    assert prediction.confidence_score >= categoriser.threshold


def test_context_categoriser_combines_mcc_and_late_night_signals() -> None:
    categoriser = ContextCategoriser()
    transaction = make_transaction(
        timestamp=datetime(2026, 11, 25, 23), mcc="5814"
    )

    prediction = categoriser.categorise(transaction)

    assert prediction.category == "Takeaways"
    assert prediction.method == "CONTEXT"
    assert "late-night" in prediction.explanation


def test_recurrence_detector_returns_regular_pattern(engine) -> None:
    repository = TransactionRepository(engine)
    dates = [datetime(2026, 10, 1), datetime(2026, 10, 8), datetime(2026, 10, 15)]
    saved = [
        repository.add(make_transaction("Gym", date, amount))
        for date, amount in zip(dates, (26.0, 30.0, 27.0))
    ]
    detector = RecurrenceDetector(engine)

    result = detector.detect(saved[-1])

    assert result.is_recurring
    assert result.interval == "weekly"
    assert result.typical_amount == 27.0
    assert result.count == 3
    assert detector.categorise(saved[-1]).category == "Subscriptions"


class _FixedCategoriser(Categoriser):
    def __init__(self, prediction: Prediction) -> None:
        self.prediction = prediction

    def categorise(self, transaction: Transaction) -> Prediction:
        return self.prediction


def test_pipeline_lowers_confidence_when_strong_methods_disagree() -> None:
    pipeline = CategorisationPipeline([
        _FixedCategoriser(Prediction("Groceries", 0.94, "Rule match", "RULE")),
        _FixedCategoriser(Prediction("Takeaways", 0.88, "ML match", "ML")),
    ])

    prediction = pipeline.categorise(make_transaction())

    assert prediction.confidence_score < 0.50
    assert "RULE predicts Groceries" in prediction.explanation
    assert "ML predicts Takeaways" in prediction.explanation
