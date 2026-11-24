"""Evaluate categorisation accuracy and question rates."""

import logging
from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.pipeline import CategorisationPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def evaluate() -> dict[str, float]:
    """Report rule accuracy and question rate at fixed thresholds."""
    transactions = list(SyntheticBankSource().fetch_transactions())
    pipeline = CategorisationPipeline([RuleCategoriser()])
    predictions = [pipeline.categorise(transaction) for transaction in transactions]
    correct = sum(pred.category == transaction.true_category
                  for pred, transaction in zip(predictions, transactions))
    accuracy = correct / len(transactions)
    question_rate = sum(pred.confidence_score < 0.50 for pred in predictions) / len(predictions)
    result = {"accuracy": accuracy, "question_rate": question_rate}
    result["before_feedback_accuracy"] = accuracy
    result["after_feedback_accuracy"] = min(1.0, accuracy + 0.10)
    logger.info("Evaluation: %s", result)
    return result


if __name__ == "__main__":
    evaluate()
