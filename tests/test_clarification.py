"""Tests for mixed-initiative decisions."""

from datetime import datetime
from expense_ai.models.transaction import Transaction, Prediction
from expense_ai.storage.database import create_database
from expense_ai.ai.clarification import ClarificationEngine
from expense_ai.storage.repository import TransactionRepository
from expense_ai.storage.database import questions_table
from sqlalchemy import select
from sqlalchemy.orm import Session


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


def test_no_duplicate_and_recurring_question(engine) -> None:
    """Repeated question types are deduplicated and recurring payments are detectable."""
    clarification = ClarificationEngine(engine)
    first = Transaction(None, datetime.now(), 12.0, "NETFLIX", "Netflix", "Birmingham")
    first.id = 1
    second = Transaction(None, datetime.now(), 12.0, "NETFLIX", "Netflix", "Birmingham")
    second.id = 2
    clarification.location_question(first)
    clarification.location_question(first)
    clarification.recurring_question(second)
    assert clarification.daily_pending_count() <= 1


def test_recurring_question_only_for_borderline_pattern_once_per_merchant(engine) -> None:
    """Regular schedules are not interrupted, and borderline schedules are asked once."""
    repository = TransactionRepository(engine)
    history = [
        Transaction(None, datetime(2026, 10, 1), 27.0, "GYM", "Gym", "Birmingham"),
        Transaction(None, datetime(2026, 10, 8), 28.0, "GYM", "Gym", "Birmingham"),
        Transaction(None, datetime(2026, 10, 19), 26.0, "GYM", "Gym", "Birmingham"),
    ]
    saved = [repository.add(item) for item in history]
    clarification = ClarificationEngine(engine)

    clarification.recurring_question(saved[-1])
    clarification.recurring_question(saved[-1])

    with Session(engine) as session:
        rows = session.execute(select(questions_table)).mappings().all()
    recurring = [row for row in rows if row["question_type"] == "RECURRING"]
    assert len(recurring) == 1
    assert "3 Gym payments" in recurring[0]["prompt_text"]
    assert "roughly every 7 days" in recurring[0]["prompt_text"]
