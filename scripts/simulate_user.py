"""Simulate app ingestion and type-correct feedback against seeded transactions."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import tempfile

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from expense_ai.models.transaction import Transaction
from expense_ai.services.app_service import AppService
from expense_ai.services.pipeline_factory import build_pipeline
from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.storage.database import metadata, questions_table


ABLATION_STAGES = {
    "rules": {"RuleCategoriser"},
    "fuzzy": {"RuleCategoriser", "FuzzyMerchantCategoriser"},
    "ml": {"RuleCategoriser", "FuzzyMerchantCategoriser", "MLCategoriser"},
    "context": {
        "RuleCategoriser",
        "FuzzyMerchantCategoriser",
        "MLCategoriser",
        "ContextCategoriser",
        "RecurrenceDetector",
    },
}


def accuracy(service: AppService) -> float:
    """Measure ingestion-time predictions against hidden synthetic labels."""
    labels = getattr(service, "_evaluation_labels", {})
    predictions = getattr(service, "_evaluation_predictions", {})
    if not labels:
        return 0.0
    return sum(
        predictions.get(transaction_id) == category
        for transaction_id, category in labels.items()
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
    months: int = 6,
    end_date: date | None = None,
    pipeline_stage: str = "context",
    with_mcc: bool = True,
    apply_feedback: bool = True,
) -> dict[str, Any]:
    """Run chronological app ingestion with a deterministic simulated clock."""
    fixed_end = end_date or date.today()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)

    with tempfile.TemporaryDirectory() as model_dir:
        model_path = Path(model_dir) / "categoriser.joblib"
        pipeline_settings = SimpleNamespace(
            MODEL_PATH=model_path,
            USE_LLM=False,
            ASK_THRESHOLD=ask_threshold,
        )
        pipeline = build_pipeline(pipeline_settings)
        allowed = ABLATION_STAGES[pipeline_stage]
        pipeline.categorisers = [
            categoriser for categoriser in pipeline.categorisers
            if categoriser.__class__.__name__ in allowed
        ]
        service = AppService(
            engine,
            pipeline,
            model_path=model_path,
            enable_ml_training="MLCategoriser" in allowed,
        )
        service.configure_clarification(
            auto_threshold, ask_threshold, question_cap
        )

        source_transactions = list(SyntheticBankSource(
            seed=7, months=months, end_date=fixed_end
        ).fetch_transactions())
        if not with_mcc:
            for transaction in source_transactions:
                transaction.mcc = None
        grouped_by_day: dict[date, list[Transaction]] = defaultdict(list)
        for transaction in source_transactions:
            grouped_by_day[transaction.timestamp.date()].append(transaction)

        start_day = min(grouped_by_day)
        total_days = (fixed_end - start_day).days + 1
        week_count = (total_days + 6) // 7
        weekly: list[dict[str, Any]] = [
            {
                "week": index + 1,
                "week_start": (start_day + timedelta(days=index * 7)).isoformat(),
                "category_questions": 0,
                "all_questions": 0,
                "answers": 0,
                "queued_backlog": 0,
                "pending_backlog": 0,
                "accuracy": 0.0,
                "transactions": 0,
            }
            for index in range(week_count)
        ]
        labels_by_id: dict[int, str] = {}
        predictions_by_id: dict[int, str] = {}
        simulation_time = [datetime.combine(start_day, datetime.min.time())]

        for current_day in sorted(grouped_by_day):
            simulation_time[0] = datetime.combine(current_day, datetime.min.time())
            service.clarification.clock = lambda: simulation_time[0]
            source_batch = grouped_by_day[current_day]
            batch_labels = [transaction.true_category for transaction in source_batch]
            ingested = service.ingest_all(source_batch)
            week_index = min((current_day - start_day).days // 7, week_count - 1)
            for saved, true_category in zip(ingested, batch_labels):
                if saved.id is None or true_category is None:
                    continue
                labels_by_id[saved.id] = true_category
                predictions_by_id[saved.id] = saved.category
                weekly[week_index]["accuracy"] += saved.category == true_category
                weekly[week_index]["transactions"] += 1

            if apply_feedback:
                questions = service.get_pending_questions()
                answered_merchants: set[tuple[str, str]] = set()
                for question in questions:
                    transaction = service.repository.get(question["transaction_id"])
                    if transaction is None:
                        continue
                    group_key = (
                        transaction.merchant_clean, question["question_type"]
                    )
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
                        weekly[week_index]["answers"] += 1

            weekly[week_index]["queued_backlog"] = (
                service.get_queued_question_count()
            )
            weekly[week_index]["pending_backlog"] = (
                len(service.get_pending_questions())
            )

        service._evaluation_labels = labels_by_id
        service._evaluation_predictions = predictions_by_id
        with Session(engine) as session:
            questions = session.execute(
                select(
                    questions_table.c.question_type,
                    questions_table.c.created_at,
                )
            ).all()
            queued_backlog = session.execute(
                select(questions_table.c.id).where(
                    questions_table.c.status == "QUEUED"
                )
            ).all()
            pending_backlog = session.execute(
                select(questions_table.c.id).where(
                    questions_table.c.status == "PENDING"
                )
            ).all()
        for question_type, created_at in questions:
            week_index = min(
                (created_at.date() - start_day).days // 7, week_count - 1
            )
            weekly[week_index]["all_questions"] += 1
            if question_type == "CATEGORY":
                weekly[week_index]["category_questions"] += 1

        accuracy_groups = {
            "weeks_1_2": [
                row for row in weekly if row["week"] <= 2
            ],
            "weeks_5_plus": [
                row for row in weekly if row["week"] >= 5
            ],
        }
        group_accuracy = {
            name: (
                sum(row["accuracy"] for row in rows)
                / sum(row["transactions"] for row in rows)
                if sum(row["transactions"] for row in rows) else 0.0
            )
            for name, rows in accuracy_groups.items()
        }
        return {
            "pipeline_stage": pipeline_stage,
            "with_mcc": with_mcc,
            "apply_feedback": apply_feedback,
            "accuracy": accuracy(service),
            "week_1_2_accuracy": group_accuracy["weeks_1_2"],
            "week_5_plus_accuracy": group_accuracy["weeks_5_plus"],
            "week_5_plus_transactions": sum(
                row["transactions"] for row in accuracy_groups["weeks_5_plus"]
            ),
            "category_questions_per_week": (
                sum(row["category_questions"] for row in weekly) / week_count
            ),
            "daily_question_cap": question_cap,
            "total_category_questions": sum(
                row["category_questions"] for row in weekly
            ),
            "queued_backlog": len(queued_backlog),
            "pending_backlog": len(pending_backlog),
            "weeks": week_count,
            "weekly": weekly,
        }
