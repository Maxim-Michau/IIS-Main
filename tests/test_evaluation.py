"""Tests for type-correct simulated-user answers and daily question caps."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from expense_ai.ai.clarification import ClarificationEngine
from expense_ai.models.transaction import Transaction
from expense_ai.storage.database import questions_table
from scripts.simulate_user import simulated_answer


def test_simulated_user_answers_only_matching_question_types() -> None:
    transaction = Transaction(
        None, datetime(2026, 11, 25), 25.0, "TESCO", "Tesco", "Birmingham"
    )

    assert simulated_answer("CATEGORY", transaction, "Groceries") == "Groceries"
    assert simulated_answer("LOCATION", transaction, "Groceries") == "Birmingham"
    assert simulated_answer("RECURRING", transaction, "Groceries") == "No"
    assert simulated_answer("EXTRA_INFO", transaction, "Groceries") is None


def test_daily_cap_counts_answered_questions(engine) -> None:
    now = datetime(2026, 11, 25, 12)
    clarification = ClarificationEngine(
        engine, max_questions_per_day=1, clock=lambda: now
    )
    first = Transaction(None, now, 10.0, "Tesco", "Tesco", "Birmingham")
    first.id = 1
    clarification._create_question(first, "CATEGORY", "Category?", ["Groceries"])
    with Session(engine) as session:
        question_id = session.execute(select(questions_table.c.id)).scalar_one()

    clarification.answer_question(question_id, "Groceries")
    second = Transaction(None, now, 10.0, "Aldi", "Aldi", "Birmingham")
    second.id = 2
    clarification._create_question(second, "CATEGORY", "Category?", ["Groceries"])

    assert clarification.daily_question_count() == 1
    assert clarification.daily_pending_count() == 0
    with Session(engine) as session:
        assert len(session.execute(select(questions_table)).all()) == 1
