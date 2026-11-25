"""Tests for transaction persistence."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.storage.repository import TransactionRepository
from expense_ai.services.app_service import AppService
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.storage.database import activity_log_table, feedback_table, questions_table
from sqlalchemy import insert, select
from sqlalchemy.orm import Session


def test_transaction_crud(engine) -> None:
    """Repository supports create, read, update and delete."""
    repository = TransactionRepository(engine)
    transaction = Transaction(
        id=None,
        timestamp=datetime(2026, 1, 1, 12),
        amount=12.50,
        merchant_raw="TESCO STORES",
        merchant_clean="tesco",
        location="Birmingham",
    )
    created = repository.add(transaction)
    assert created.id is not None
    assert repository.get(created.id).merchant_clean == "tesco"
    created.category = "Groceries"
    repository.update(created)
    assert repository.get(created.id).category == "Groceries"
    assert repository.delete(created.id)
    assert repository.get(created.id) is None


def test_ingest_batch_creates_answerable_questions(engine) -> None:
    """Ingestion creates questions and answering creates confirmed feedback."""
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    batch = [
        Transaction(None, datetime(2026, 11, 24, 12), 42.0,
                    "PAYPAL *UNKNOWN", "paypal unknown", None,
                    true_category="Shopping"),
        Transaction(None, datetime(2026, 11, 24, 13), 130.0,
                    "SQ *UNKNOWN CAFE", "Unknown Cafe", "Manchester",
                    true_category="Eating Out"),
    ]
    ingested = service.ingest_all(batch)
    questions = service.get_pending_questions()
    assert questions
    paypal = next(item for item in ingested if item.merchant_clean == "paypal unknown")
    question = next(item for item in questions if item["transaction_id"] == paypal.id)
    confirmed_category = paypal.category
    service.answer_question(question["id"], confirmed_category)
    transaction = service.repository.get(paypal.id)
    assert transaction.status == "CONFIRMED"
    with Session(engine) as session:
        feedback = session.execute(select(feedback_table)).all()
    assert feedback

    repeat = Transaction(None, datetime(2026, 11, 25, 12), 44.0,
                         "PAYPAL *UNKNOWN", "paypal unknown", None,
                         true_category="Shopping")
    service.ingest(repeat)
    repeat_questions = [
        item for item in service.get_pending_questions()
        if item["transaction_id"] == repeat.id
        and item["question_type"] == "CATEGORY"
    ]
    assert repeat_questions == []


def test_location_answer_preserves_category_and_updates_location(engine) -> None:
    """Location answers update location without corrupting the category."""
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    transaction = service.repository.add(Transaction(
        None, datetime.now(), 12.0, "Greggs", "Greggs", "Unknown",
        category="Eating Out", status="TENTATIVE",
    ))
    with Session(engine) as session:
        question_id = session.execute(insert(questions_table).values(
            transaction_id=transaction.id,
            question_type="LOCATION",
            prompt_text="Where?",
            options="",
            status="PENDING",
        )).inserted_primary_key[0]
        session.commit()

    service.answer_question(question_id, "Birmingham")

    updated = service.repository.get(transaction.id)
    assert updated.category == "Eating Out"
    assert updated.location == "Birmingham"
    with Session(engine) as session:
        assert session.execute(select(feedback_table)).all() == []


def test_yes_no_answer_does_not_become_a_category(engine) -> None:
    """Recurring answers are stored as flags and never become category feedback."""
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    transaction = service.repository.add(Transaction(
        None, datetime.now(), 12.0, "Netflix", "Netflix", "Birmingham",
        category="Subscriptions",
    ))
    with Session(engine) as session:
        question_id = session.execute(insert(questions_table).values(
            transaction_id=transaction.id,
            question_type="RECURRING",
            prompt_text="Recurring?",
            options="Yes|No",
            status="PENDING",
        )).inserted_primary_key[0]
        session.commit()

    service.answer_question(question_id, "Yes")

    updated = service.repository.get(transaction.id)
    assert updated.category == "Subscriptions"
    assert updated.is_recurring is True
    with Session(engine) as session:
        assert session.execute(select(feedback_table)).all() == []


def test_merchant_answer_updates_pending_transactions_and_logs_once(engine) -> None:
    """A merchant answer updates all its pending rows but records feedback once."""
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    transaction_ids = []
    question_ids = []
    for day in (1, 2, 3):
        transaction = service.repository.add(Transaction(
            None, datetime(2026, 11, day), 9.0, "GREGGS", "Greggs", "Birmingham",
            category="Other", status="TENTATIVE",
        ))
        transaction_ids.append(transaction.id)
        with Session(engine) as session:
            question_id = session.execute(insert(questions_table).values(
                transaction_id=transaction.id,
                question_type="CATEGORY",
                prompt_text="Category?",
                options="Eating Out|Takeaways",
                status="PENDING",
            )).inserted_primary_key[0]
            session.commit()
        question_ids.append(question_id)

    message = service.answer_question(question_ids[0], "Eating Out")

    assert message == "Set Greggs to Eating Out for 3 transactions."
    assert all(
        service.repository.get(transaction_id).category == "Eating Out"
        for transaction_id in transaction_ids
    )
    with Session(engine) as session:
        assert len(session.execute(select(feedback_table)).all()) == 1
        assert len(session.execute(select(activity_log_table)).all()) == 3
