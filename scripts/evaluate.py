"""Evaluate categorisation accuracy and question/error rates."""

import logging
from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.pipeline import CategorisationPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def evaluate() -> dict[str, float | dict[str, float]]:
    """Report measured rule accuracy and rates at several thresholds."""
    transactions = list(SyntheticBankSource().fetch_transactions())
    pipeline = CategorisationPipeline([RuleCategoriser()])
    predictions = [pipeline.categorise(transaction) for transaction in transactions]
    correct = sum(pred.category == transaction.true_category
                  for pred, transaction in zip(predictions, transactions))
    accuracy = correct / len(transactions)
    total = len(predictions)
    thresholds: dict[str, float] = {}
    for threshold in (0.50, 0.65, 0.85):
        questions = sum(pred.confidence_score < threshold for pred in predictions)
        errors = sum(
            pred.category != transaction.true_category
            and pred.confidence_score >= threshold
            for pred, transaction in zip(predictions, transactions)
        )
        thresholds[f"{threshold:.2f}"] = {
            "question_rate": questions / total,
            "error_rate": errors / total,
        }
    result = {
        "accuracy": accuracy,
        "question_rate": thresholds["0.50"]["question_rate"],
        "thresholds": thresholds,
        "transactions": float(total),
    }
    logger.info("Evaluation: %s", result)
    return result


if __name__ == "__main__":
    evaluate()
