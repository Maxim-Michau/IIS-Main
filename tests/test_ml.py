"""Tests for the optional ML categoriser."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.ai.categorisers.ml import MLCategoriser
import tempfile
from expense_ai.services.app_service import AppService
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.feedback import FeedbackLearner
from expense_ai.storage.repository import TransactionRepository
from expense_ai.storage.database import feedback_table
from sqlalchemy import insert
from sqlalchemy.orm import Session


def test_ml_low_confidence_before_training(tmp_path) -> None:
    """An untrained model fails safely with low confidence."""
    categoriser = MLCategoriser(tmp_path / "missing.joblib")
    prediction = categoriser.categorise(
        Transaction(None, datetime.now(), 10.0, "Tesco", "Tesco", "Birmingham")
    )
    assert prediction.confidence_score < 0.50


def test_ml_training_uses_feedback_not_true_category(engine, tmp_path, monkeypatch) -> None:
    """Feedback labels train ML; synthetic true_category is ignored."""
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    learner = FeedbackLearner(engine, promotion_count=100)
    transactions = []
    for index in range(10):
        category = "Groceries" if index < 5 else "Transport"
        transaction = Transaction(
            None, datetime(2026, 11, 24, 12), 10.0,
            f"MERCHANT {index}", f"Merchant {index}", "Birmingham",
            category=category, status="TENTATIVE",
            true_category="Never-Use-This",
        )
        saved = service.ingest(transaction)
        learner.record_answer(saved, category, category)
        saved.status = "CONFIRMED"
        service.repository.update(saved)
        transactions.append(transaction)
    captured = {}

    def capture_train(self, merchants, categories, amounts, hours):
        captured["categories"] = list(categories)
        captured["merchants"] = list(merchants)
        self.model = ("trained", object())
        self.model_path = tmp_path / "feedback.joblib"

    monkeypatch.setattr(MLCategoriser, "train", capture_train)
    assert service.train_ml_if_ready()
    assert set(captured["categories"]) == {"Groceries", "Transport"}
    assert "Never-Use-This" not in captured["categories"]


def test_single_example_category_does_not_block_training(engine, tmp_path, monkeypatch) -> None:
    """A custom category with one example is excluded from otherwise valid training."""
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    repository = TransactionRepository(engine)
    categories = ["Groceries"] * 5 + ["Transport"] * 5 + ["Custom"]
    for index, category in enumerate(categories):
        transaction = repository.add(Transaction(
            None, datetime(2026, 11, 24, 12), 10.0,
            f"MERCHANT {index}", f"Merchant {index}", "Birmingham",
            category=category, method="USER",
        ))
        with Session(engine) as session:
            session.execute(insert(feedback_table).values(
                transaction_id=transaction.id,
                predicted_category="Other",
                chosen_category=category,
                merchant_clean=transaction.merchant_clean,
                created_at=datetime.now(),
            ))
            session.commit()
    captured = {}

    def capture_train(self, merchants, selected_categories, amounts, hours):
        captured["categories"] = list(selected_categories)
        self.model = ("trained", object())

    monkeypatch.setattr(MLCategoriser, "train", capture_train)
    assert service.train_ml_if_ready()
    assert len(captured["categories"]) == 10
    assert "Custom" not in captured["categories"]


def test_corrupt_ml_model_file_falls_back_to_untrained(tmp_path) -> None:
    """A corrupt model file is logged and does not prevent categoriser startup."""
    model_path = tmp_path / "corrupt.joblib"
    model_path.write_bytes(b"not a joblib model")

    categoriser = MLCategoriser(model_path)

    assert not categoriser.is_trained()
