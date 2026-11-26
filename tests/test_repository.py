"""Tests for transaction persistence."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.storage.repository import TransactionRepository
from expense_ai.services.app_service import AppService
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.storage.database import (
    activity_log_table, budgets_table, feedback_table, insights_table, metadata,
    questions_table, merchant_rules_table, transactions_table,
)
from sqlalchemy import func, insert, select
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
    """A merchant answer updates eligible rows and records one reversible action."""
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
    protected = service.repository.add(Transaction(
        None, datetime(2026, 11, 4), 35.0, "GREGGS", "Greggs", "Birmingham",
        category="Shopping", status="CONFIRMED", method="USER",
        confidence_score=1.0, explanation="Confirmed by you on an earlier date",
    ))

    message = service.answer_question(question_ids[0], "Eating Out")

    assert message == "Confirmed Greggs as Eating Out; updated 3 transactions."
    updated = [service.repository.get(transaction_id) for transaction_id in transaction_ids]
    assert all(item.category == "Eating Out" for item in updated)
    assert all(item.method == "USER" and item.confidence_score == 1.0 for item in updated)
    assert all(item.status == "CORRECTED" for item in updated)
    assert service.repository.get(protected.id).category == "Shopping"
    with Session(engine) as session:
        assert len(session.execute(select(feedback_table)).all()) == 1
        assert len(session.execute(select(activity_log_table)).all()) == 1
        action = session.execute(select(activity_log_table)).mappings().one()
        assert action["previous_state"]
        rule = session.execute(select(merchant_rules_table)).mappings().one()
        assert rule["category"] == "Eating Out"
        assert rule["times_confirmed"] == 1

    assert service.undo_category_change(transaction_ids[0])
    restored = [service.repository.get(transaction_id) for transaction_id in transaction_ids]
    assert all(item.category == "Other" for item in restored)
    assert all(item.status == "TENTATIVE" for item in restored)
    assert all(item.method == "RULE" and item.confidence_score == 0.0 for item in restored)
    with Session(engine) as session:
        assert session.execute(select(feedback_table)).all() == []
        assert session.execute(select(merchant_rules_table)).all() == []
        statuses = session.execute(
            select(questions_table.c.status).order_by(questions_table.c.id)
        ).scalars().all()
    assert statuses == ["PENDING", "PENDING", "PENDING"]


def test_manual_category_correction_uses_learning_path_and_validates(engine) -> None:
    """Manual corrections validate input and immediately teach merchant rules."""
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    transaction = service.repository.add(Transaction(
        None, datetime.now(), 14.0, "ODD MERCHANT", "Odd Merchant", "Birmingham",
        category="Other", status="TENTATIVE",
    ))

    try:
        service.correct_category(transaction.id, "  ")
    except ValueError as error:
        assert str(error) == "Category cannot be empty"
    else:
        raise AssertionError("An empty category should be rejected")

    service.correct_category(transaction.id, "  Groceries  ")

    updated = service.repository.get(transaction.id)
    assert updated.category == "Groceries"
    assert updated.status == "CORRECTED"
    assert updated.method == "USER"
    prediction = service.pipeline.categorise(Transaction(
        None, datetime.now(), 12.0, "ODD MERCHANT", "Odd Merchant", "Birmingham",
    ))
    assert prediction.category == "Groceries"
    assert prediction.method == "LEARNED"


def test_reset_demo_data_clears_all_tables_and_model(engine, tmp_path) -> None:
    """Reset removes every persisted record and the configured model file."""
    model_path = tmp_path / "categoriser.joblib"
    model_path.write_bytes(b"model")
    service = AppService(
        engine, CategorisationPipeline([]), model_path=model_path
    )
    with Session(engine) as session:
        transaction_id = session.execute(insert(transactions_table).values(
            timestamp=datetime(2026, 11, 1),
            amount=10.0,
            merchant_raw="TESCO",
            merchant_clean="Tesco",
            category="Groceries",
            confidence_score=1.0,
            status="CONFIRMED",
            source="TEST",
            method="USER",
            is_recurring=False,
        )).inserted_primary_key[0]
        session.execute(insert(questions_table).values(
            transaction_id=transaction_id,
            question_type="CATEGORY",
            prompt_text="Category?",
            status="ANSWERED",
        ))
        session.execute(insert(feedback_table).values(
            transaction_id=transaction_id,
            predicted_category="Other",
            chosen_category="Groceries",
            merchant_clean="Tesco",
            created_at=datetime(2026, 11, 1),
        ))
        session.execute(insert(budgets_table).values(
            category="Groceries", monthly_limit=100.0, month="2026-11"
        ))
        session.execute(insert(merchant_rules_table).values(
            pattern="tesco",
            category="Groceries",
            origin="LEARNED",
            times_confirmed=1,
        ))
        session.execute(insert(insights_table).values(
            title="Save more",
            explanation="A test insight",
            estimated_monthly_saving=10.0,
            status="PENDING",
        ))
        session.execute(insert(activity_log_table).values(
            transaction_id=transaction_id,
            event_type="ANSWER",
            message="Confirmed category",
            created_at=datetime(2026, 11, 1),
        ))
        session.commit()

    service.reset_demo_data()

    assert not model_path.exists()
    with Session(engine) as session:
        counts = {
            table.name: session.execute(
                select(func.count()).select_from(table)
            ).scalar_one()
            for table in metadata.sorted_tables
        }
    assert all(count == 0 for count in counts.values()), counts
