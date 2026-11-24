"""Tests for the optional ML categoriser."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.ai.categorisers.ml import MLCategoriser
import tempfile


def test_ml_low_confidence_before_training(tmp_path) -> None:
    """An untrained model fails safely with low confidence."""
    categoriser = MLCategoriser(tmp_path / "missing.joblib")
    prediction = categoriser.categorise(
        Transaction(None, datetime.now(), 10.0, "Tesco", "Tesco", "Birmingham")
    )
    assert prediction.confidence_score < 0.50
