"""Measure type-correct feedback against seeded synthetic transactions."""

from collections import defaultdict
from datetime import date, datetime, timedelta
import math
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from expense_ai.ai.categorisers.context import ContextCategoriser
from expense_ai.ai.categorisers.fuzzy import FuzzyMerchantCategoriser
from expense_ai.ai.categorisers.recurrence import RecurrenceDetector
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.models.transaction import Transaction
from expense_ai.services.app_service import AppService
from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.storage.database import metadata, questions_table


def accuracy(service: AppService) -> float:
    """Measure stored category accuracy against hidden simulated labels."""
    labels = getattr(service, "_evaluation_labels", {})
    transactions = service.get_transactions()
    if not labels:
        return 0.0
    return sum(
        item.category == labels.get(item.id)
        for item in transactions
        if item.id in labels
    ) / len(labels)


def simulated_answer(
    question_type: str,
    transaction: Transaction,
    true_category: str | None,
) -> str | None:
    """Return only type-compatible simulated answers; skip free-text details."""
    if question_type == "CATEGORY":
        return true_category
    if question_type == "LOCATION":
        return transaction.location or "Birmingham"
    if question_type == "RECURRING":
        return "No"
    if question_type == "EXTRA_INFO":
        return None
    return None


def run_simulation(
    auto_threshold: float = 0.85,
    ask_threshold: float = 0.50,
    question_cap: int = 5,
    months: int = 4,
    end_date: date | None = None,
) -> dict[str, Any]:
    """Ingest transactions by simulated day with the configured daily cap."""
    fixed_end = end_date or date.today()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    pipeline = CategorisationPipeline([
        RuleCategoriser(),
        FuzzyMerchantCategoriser(),
        ContextCategoriser(),
        RecurrenceDetector(),
    ])
    service = AppService(engine, pipeline)
    service.configure_clarification(auto_threshold, ask_threshold, question_cap)
    source_transactions = list(SyntheticBankSource(
        seed=7, months=months, end_date=fixed_end
    ).fetch_transactions())
    grouped_by_day: dict[date, list[Transaction]] = defaultdict(list)
    for transaction in source_transactions:
        grouped_by_day[transaction.timestamp.date()].append(transaction)

    start_day = min(grouped_by_day)
    total_days = (fixed_end - start_day).days + 1
    week_count = math.ceil(total_days / 7)
    weekly = [
        {
            "week": index + 1,
            "week_start": (start_day + timedelta(days=index * 7)).isoformat(),
            "category_questions": 0,
            "all_questions": 0,
            "answers": 0,
        }
        for index in range(week_count)
    ]
    labels_by_id: dict[int, str] = {}
    initial_correct = 0
    initial_count = 0

    for current_day in sorted(grouped_by_day):
        service.clarification.clock = lambda current_day=current_day: datetime.combine(
            current_day, datetime.min.time()
        )
        for source in grouped_by_day[current_day]:
            true_category = source.true_category
            ingested = service.ingest(source)
            if ingested.id is None or true_category is None:
                continue
            labels_by_id[ingested.id] = true_category
            initial_correct += ingested.category == true_category
            initial_count += 1

        pending = service.get_pending_questions()
        answered_merchants: set[tuple[str, str]] = set()
        for question in pending:
            transaction = service.repository.get(question["transaction_id"])
            if transaction is None:
                continue
            group_key = (transaction.merchant_clean, question["question_type"])
            if group_key in answered_merchants:
                continue
            answer = simulated_answer(
                question["question_type"],
                transaction,
                labels_by_id.get(transaction.id),
            )
            if answer is None:
                continue
            if service.answer_question(question["id"], answer):
                answered_merchants.add(group_key)
                index = min((current_day - start_day).days // 7, week_count - 1)
                weekly[index]["answers"] += 1

    service._evaluation_labels = labels_by_id
    with Session(engine) as session:
        questions = session.execute(
            select(questions_table.c.question_type, questions_table.c.created_at)
        ).all()
    for question_type, created_at in questions:
        week_index = min((created_at.date() - start_day).days // 7, week_count - 1)
        weekly[week_index]["all_questions"] += 1
        if question_type == "CATEGORY":
            weekly[week_index]["category_questions"] += 1

    category_question_total = sum(int(row["category_questions"]) for row in weekly)
    all_question_total = sum(int(row["all_questions"]) for row in weekly)
    after_accuracy = accuracy(service)
    return {
        "before_accuracy": initial_correct / initial_count if initial_count else 0.0,
        "after_accuracy": after_accuracy,
        "error_rate": 1.0 - after_accuracy,
        "category_questions": category_question_total,
        "all_questions": all_question_total,
        "category_questions_per_week": category_question_total / week_count,
        "all_questions_per_week": all_question_total / week_count,
        "daily_question_cap": question_cap,
        "weeks": week_count,
        "weekly": weekly,
    }
