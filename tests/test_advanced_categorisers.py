"""Tests for context-based and fuzzy categorisation methods."""

from datetime import datetime, timedelta

from expense_ai.ai.categorisers.base import Categoriser
from expense_ai.ai.categorisers.context import ContextCategoriser
from expense_ai.ai.categorisers.fuzzy import FuzzyMerchantCategoriser
from expense_ai.ai.categorisers.recurrence import RecurrenceDetector
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.categorisers.llm import LLMCategoriser
from expense_ai.ai.clarification import ClarificationEngine
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
    assert saved[-1].is_recurring
    assert detector.categorise(saved[-1]).method == "RECURRENCE"


def test_recurrence_accepts_patterns_with_eighty_percent_regular_payments(engine) -> None:
    """A small number of amount and date outliers do not hide a recurring pattern."""
    repository = TransactionRepository(engine)
    start = datetime(2026, 10, 1)
    for offset, amount in zip((0, 7, 14, 24, 31), (100.0, 102.0, 98.0, 160.0, 105.0)):
        repository.add(make_transaction(
            "Gym", start + timedelta(days=offset), amount
        ))
    incoming = make_transaction("Gym", start + timedelta(days=38), 95.0)

    result = RecurrenceDetector(engine).detect(incoming)

    assert result.is_recurring
    assert result.interval == "weekly"


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


def test_context_and_recurrence_cannot_create_label_conflict() -> None:
    pipeline = CategorisationPipeline([
        _FixedCategoriser(Prediction("Groceries", 0.90, "Rule", "RULE")),
        _FixedCategoriser(Prediction("Subscriptions", 0.90, "Regular payer", "RECURRENCE")),
        _FixedCategoriser(Prediction("Takeaways", 0.90, "History", "CONTEXT")),
    ])

    prediction = pipeline.categorise(make_transaction())

    assert prediction.category == "Groceries"
    assert prediction.confidence_score == 0.85
    assert "disagree" not in prediction.explanation


def test_rent_and_weekly_tesco_are_auto_accepted(engine) -> None:
    repository = TransactionRepository(engine)
    history = [
        ("Rent", datetime(2026, 10, 1), 650.0, "Rent & Bills"),
        ("Rent", datetime(2026, 11, 1), 650.0, "Rent & Bills"),
        ("Rent", datetime(2026, 12, 1), 650.0, "Rent & Bills"),
        ("Tesco", datetime(2026, 10, 1), 18.0, "Groceries"),
        ("Tesco", datetime(2026, 10, 8), 20.0, "Groceries"),
        ("Tesco", datetime(2026, 10, 15), 19.0, "Groceries"),
    ]
    for merchant, timestamp, amount, category in history:
        repository.add(make_transaction(
            merchant, timestamp, amount, category=category, status="CONFIRMED"
        ))
    pipeline = CategorisationPipeline([
        RuleCategoriser(engine=engine),
        ContextCategoriser(engine),
        RecurrenceDetector(engine),
    ])

    rent = make_transaction("Rent", datetime(2026, 12, 31), 650.0)
    tesco = make_transaction("Tesco", datetime(2026, 10, 22), 18.5)

    rent_prediction = pipeline.categorise(rent)
    tesco_prediction = pipeline.categorise(tesco)

    assert rent_prediction.category == "Rent & Bills"
    assert ClarificationEngine(engine).decide(rent, rent_prediction) == "AUTO"
    assert rent.is_recurring
    assert tesco_prediction.category == "Groceries"
    assert ClarificationEngine(engine).decide(tesco, tesco_prediction) == "AUTO"
    assert tesco.is_recurring


def test_netflix_is_not_assigned_groceries_from_other_merchant_history(engine) -> None:
    repository = TransactionRepository(engine)
    repository.add(make_transaction(
        "Tesco", datetime(2026, 10, 1), 20.0,
        category="Groceries", status="CONFIRMED",
    ))
    pipeline = CategorisationPipeline([
        RuleCategoriser(engine=engine),
        ContextCategoriser(engine),
        RecurrenceDetector(engine),
    ])

    prediction = pipeline.categorise(make_transaction("Netflix"))

    assert prediction.category == "Subscriptions"
    assert prediction.method == "RULE"


def test_llm_is_skipped_for_confident_rule_and_cached_per_merchant() -> None:
    class CountingClient:
        def __init__(self) -> None:
            self.calls = 0

        class Messages:
            def __init__(self, owner: "CountingClient") -> None:
                self.owner = owner

            def create(self, **kwargs: object) -> object:
                self.owner.calls += 1

                class Block:
                    text = (
                        '{"category":"Groceries","confidence":0.9,'
                        '"reason":"Food purchase"}'
                    )

                class Response:
                    content = [Block()]

                return Response()

        @property
        def messages(self) -> "CountingClient.Messages":
            return self.Messages(self)

    confident_client = CountingClient()
    confident_pipeline = CategorisationPipeline([
        RuleCategoriser(),
        LLMCategoriser(enabled=True, client=confident_client),
    ])
    confident_pipeline.categorise(make_transaction("Netflix"))
    assert confident_client.calls == 0

    client = CountingClient()
    pipeline = CategorisationPipeline([
        RuleCategoriser(),
        ContextCategoriser(),
        RecurrenceDetector(),
        LLMCategoriser(enabled=True, client=client),
    ])
    first = make_transaction("New Merchant")
    second = make_transaction(" NEW   MERCHANT ")
    assert pipeline.categorise(first).category == "Groceries"
    assert pipeline.categorise(second).category == "Groceries"
    assert client.calls == 1
