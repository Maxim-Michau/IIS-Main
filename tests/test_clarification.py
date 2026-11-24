"""Tests for mixed-initiative decisions."""

from datetime import datetime
from expense_ai.models.transaction import Transaction, Prediction
from expense_ai.storage.database import create_database
from expense_ai.ai.clarification import ClarificationEngine


def test_threshold_decisions(engine) -> None:
    """Confidence controls automatic and tentative decisions."""
    clarification = ClarificationEngine(engine)
    transaction = Transaction(None, datetime.now(), 10.0, "Tesco", "Tesco", "Birmingham")
    transaction.id = 1
    assert clarification.decide(transaction, Prediction("Groceries", 0.90, "Test", "RULE")) == "AUTO"
    assert clarification.decide(transaction, Prediction("Groceries", 0.70, "Test", "ML")) == "TENTATIVE"
    assert clarification.decide(transaction, Prediction("Other", 0.40, "Test", "ML")) == "ASK"


def test_daily_question_cap(engine) -> None:
    """The clarification engine stops at the configured cap."""
    clarification = ClarificationEngine(engine, max_questions_per_day=1)
    first = Transaction(None, datetime.now(), 10.0, "Tesco", "Tesco", "Birmingham")
    first.id = 1
    second = Transaction(None, datetime.now(), 11.0, "Amazon", "Amazon", "Birmingham")
    second.id = 2
    clarification.decide(first, Prediction("Groceries", 0.40, "Test", "ML"))
    clarification.decide(second, Prediction("Shopping", 0.40, "Test", "ML"))
    assert clarification.daily_pending_count() == 1
