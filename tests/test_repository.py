"""Tests for transaction persistence."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.storage.repository import TransactionRepository
from expense_ai.services.app_service import AppService
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.storage.database import feedback_table
from sqlalchemy import select
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
