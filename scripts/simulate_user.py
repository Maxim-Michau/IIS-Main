"""Measure feedback learning using only questions created by the app."""

import logging

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.services.app_service import AppService
from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.storage.database import metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def accuracy(service: AppService) -> float:
    """Measure stored category accuracy against the hidden simulated labels."""
    return getattr(service, "_accuracy", 0.0)


def run_simulation(auto_threshold: float = 0.85,
                   ask_threshold: float = 0.50,
                   question_cap: int = 5) -> dict[str, object]:
    """Ingest weekly batches and answer only questions that ClarificationEngine created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    service.configure_clarification(auto_threshold, ask_threshold, question_cap)
    transactions = list(SyntheticBankSource(seed=7, months=4).fetch_transactions())
    hidden_labels = {
        (item.timestamp, item.merchant_raw, item.amount): item.true_category
        for item in transactions
    }
    before = 0
    weekly: list[dict[str, object]] = []
    labels_by_id: dict[int, str] = {}

    batch_size = 90
    for week in range(1, 5):
        batch = transactions[(week - 1) * batch_size:week * batch_size]
        ingested = service.ingest_all(batch)
        for item in ingested:
            labels_by_id[item.id] = hidden_labels[
                (item.timestamp, item.merchant_raw, item.amount)
            ]
        pending_before_answer = list(service.get_pending_questions())
        batch_ids = {item.id for item in ingested}
        pending_before_answer = [
            question for question in pending_before_answer
            if question["transaction_id"] in batch_ids
        ]
        answered = 0
        for question in pending_before_answer:
            transaction_id = question["transaction_id"]
            transaction = service.repository.get(transaction_id)
            if transaction is None:
                continue
            matched = next((item for item in ingested if item.id == transaction_id), None)
            hidden_category = hidden_labels.get(
                (matched.timestamp, matched.merchant_raw, matched.amount)
            ) if matched is not None else None
            if hidden_category:
                service.answer_question(question["id"], hidden_category)
                answered += 1

        stored = service.get_transactions()
        correct = sum(
            item.category == labels_by_id.get(item.id)
            for item in stored
            if item.id in labels_by_id
        )
        after_accuracy = correct / len(labels_by_id) if labels_by_id else 0.0
        if week == 1:
            before = sum(
                item.category == labels_by_id[item.id]
                for item in ingested
            )
            before /= len(ingested) if ingested else 1
        weekly.append({
            "week": week,
            "questions": len(pending_before_answer),
            "answers": answered,
            "accuracy": after_accuracy,
        })

    return {
        "before_accuracy": before,
        "after_accuracy": weekly[-1]["accuracy"] if weekly else 0.0,
        "weekly": weekly,
    }


def main() -> None:
    """Print measured results for several real threshold settings."""
    for auto_threshold, ask_threshold in ((0.95, 0.70), (0.85, 0.50), (0.70, 0.30)):
        result = run_simulation(auto_threshold, ask_threshold, question_cap=100)
        logger.info("Threshold %.2f/%.2f: %s", auto_threshold, ask_threshold, result)


if __name__ == "__main__":
    main()
