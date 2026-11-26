"""Tests for mixed-initiative decisions."""

from datetime import datetime, timedelta
from sqlalchemy import func
from expense_ai.models.transaction import Transaction, Prediction
from expense_ai.ai.clarification import ClarificationEngine
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.storage.repository import TransactionRepository
from expense_ai.storage.database import questions_table, transactions_table
from expense_ai.services.app_service import AppService
from sqlalchemy import select
from sqlalchemy.orm import Session
import pytest


def test_threshold_decisions(engine) -> None:
    """Confidence controls automatic and tentative decisions."""
    clarification = ClarificationEngine(engine)
    transaction = Transaction(None, datetime.now(), 10.0, "Tesco", "Tesco", "Birmingham")
    transaction.id = 1
    assert clarification.decide(transaction, Prediction("Groceries", 0.90, "Test", "RULE")) == "AUTO"
    assert clarification.decide(transaction, Prediction("Groceries", 0.70, "Test", "ML")) == "TENTATIVE"
    assert clarification.decide(transaction, Prediction("Other", 0.40, "Test", "ML")) == "ASK"


def test_settings_reject_auto_threshold_not_above_question_threshold(engine) -> None:
    """Clarification configuration enforces the threshold ordering invariant."""
    service = AppService(engine, CategorisationPipeline([]))

    with pytest.raises(ValueError, match="must exceed"):
        service.configure_clarification(0.5, 0.5, 5)


def test_daily_question_cap(engine) -> None:
    """The daily cap limits surfaced questions but retains the rest in the queue."""
    clarification = ClarificationEngine(engine, max_questions_per_day=1)
    first = Transaction(None, datetime.now(), 10.0, "Tesco", "Tesco", "Birmingham")
    first.id = 1
    second = Transaction(None, datetime.now(), 11.0, "Amazon", "Amazon", "Birmingham")
    second.id = 2
    clarification.decide(first, Prediction("Groceries", 0.40, "Test", "ML"))
    clarification.decide(second, Prediction("Shopping", 0.40, "Test", "ML"))
    assert clarification.daily_pending_count() == 1
    with Session(engine) as session:
        assert session.execute(
            select(func.count()).select_from(questions_table).where(
                questions_table.c.status == "QUEUED"
            )
        ).scalar_one() == 1


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


def test_bulk_questions_queue_and_release_by_priority(engine) -> None:
    """Bulk history is retained, and answering does not free today's surfaced slot."""
    current_time = [datetime(2026, 11, 25, 12)]
    clarification = ClarificationEngine(
        engine, max_questions_per_day=5, clock=lambda: current_time[0]
    )
    repository = TransactionRepository(engine)
    for index in range(200):
        transaction = repository.add(Transaction(
            None, current_time[0] - timedelta(days=index), float(index + 1),
            f"MERCHANT {index}", f"Merchant {index}", "Birmingham",
            category="Other", confidence_score=0.2,
        ))
        clarification._create_question(
            transaction, "CATEGORY", "What category?", ["Other"]
        )

    assert clarification.release_questions() == 5
    with Session(engine) as session:
        assert session.execute(
            select(func.count()).select_from(questions_table).where(
                questions_table.c.status == "PENDING"
            )
        ).scalar_one() == 5
        assert session.execute(
            select(func.count()).select_from(questions_table).where(
                questions_table.c.status == "QUEUED"
            )
        ).scalar_one() == 195
        first_question = session.execute(
            select(questions_table.c.id)
            .join(
                transactions_table,
                questions_table.c.transaction_id == transactions_table.c.id,
            )
            .where(questions_table.c.status == "PENDING")
            .order_by(transactions_table.c.amount.desc())
            .limit(1)
        ).scalar_one()

    clarification.answer_question(first_question, "Groceries")
    assert clarification.release_questions() == 0

    current_time[0] += timedelta(days=1)
    assert clarification.release_questions() == 5
    with Session(engine) as session:
        surfaced = session.execute(
            select(transactions_table.c.amount)
            .join(
                questions_table,
                questions_table.c.transaction_id == transactions_table.c.id,
            )
            .where(
                questions_table.c.status == "PENDING",
                func.date(questions_table.c.surfaced_at) == "2026-11-26",
            )
            .order_by(transactions_table.c.amount.desc())
        ).all()
    assert surfaced[0].amount == 195.0


def test_bulk_ingestion_surfaces_only_the_daily_cap(engine) -> None:
    """The application ingests every history row but surfaces only the daily limit."""
    service = AppService(engine, CategorisationPipeline([]))
    transactions = [
        Transaction(
            None, datetime(2026, 11, 25), 10.0, f"UNKNOWN {index}",
            f"Unknown {index}", "Birmingham",
        )
        for index in range(200)
    ]

    service.ingest_all(transactions)

    assert len(service.get_pending_questions()) == service.clarification.max_questions_per_day
    assert service.get_queued_question_count() == 200 - service.clarification.max_questions_per_day


def test_location_question_uses_merchant_history_and_targets_one_transaction(engine) -> None:
    """Unusual locations use merchant history, and answers affect only the asked row."""
    service = AppService(engine, CategorisationPipeline([]))
    repository = service.repository
    repository.add(Transaction(
        None, datetime(2026, 11, 1), 20.0, "TESCO", "Tesco", "Cambridge",
        category="Groceries",
    ))
    repository.add(Transaction(
        None, datetime(2026, 11, 2), 20.0, "OTHER", "Other", "Leeds",
        category="Shopping",
    ))
    target = repository.add(Transaction(
        None, datetime(2026, 11, 3), 20.0, "TESCO", "Tesco", "Leeds",
        category="Groceries",
    ))
    untouched = repository.add(Transaction(
        None, datetime(2026, 11, 4), 20.0, "TESCO", "Tesco", "Cambridge",
        category="Groceries",
    ))
    service.clarification.location_question(target)
    with Session(engine) as session:
        question = session.execute(
            select(questions_table).where(
                questions_table.c.transaction_id == target.id,
                questions_table.c.question_type == "LOCATION",
            )
        ).mappings().one()
        assert question["status"] == "QUEUED"
        assert question["options"] == "Cambridge"
        assert "previous payments were in Cambridge" in question["prompt_text"]
        session.execute(
            questions_table.update().where(
                questions_table.c.id == question["id"]
            ).values(status="PENDING")
        )
        session.commit()

    service.answer_question(question["id"], "Leeds")

    assert repository.get(target.id).location == "Leeds"
    assert repository.get(untouched.id).location == "Cambridge"


def test_extra_info_requires_large_unknown_category(engine) -> None:
    """Extra-info questions are limited to large transactions without a category."""
    clarification = ClarificationEngine(engine)
    categorized = Transaction(
        None, datetime.now(), 250.0, "KNOWN", "Known", None, category="Shopping"
    )
    categorized.id = 1
    small_unknown = Transaction(
        None, datetime.now(), 99.0, "SMALL", "Small", None, category="Other"
    )
    small_unknown.id = 2
    large_unknown = Transaction(
        None, datetime.now(), 250.0, "UNKNOWN", "Unknown", None, category="Other"
    )
    large_unknown.id = 3

    clarification.extra_info_question(categorized)
    clarification.extra_info_question(small_unknown)
    clarification.extra_info_question(large_unknown)

    with Session(engine) as session:
        rows = session.execute(
            select(questions_table.c.transaction_id, questions_table.c.question_type)
        ).all()
    assert rows == [(3, "EXTRA_INFO")]
