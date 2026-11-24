"""Replay measured scripted answers and report accuracy per week."""

from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.pipeline import CategorisationPipeline


def main() -> None:
    """Simulate a three-week feedback cycle from the synthetic labels."""
    transactions = list(SyntheticBankSource(seed=7).fetch_transactions())
    pipeline = CategorisationPipeline([RuleCategoriser()])
    predictions = [pipeline.categorise(transaction) for transaction in transactions]
    learned: dict[str, str] = {}
    for week in range(1, 5):
        answered = 0
        for transaction, prediction in zip(transactions, predictions):
            if transaction.merchant_clean not in learned:
                continue
            answered += 1
            prediction.category = learned[transaction.merchant_clean]
        batch = transactions[(week - 1) * 30:week * 30]
        for transaction in batch:
            if transaction.true_category and transaction.merchant_clean not in learned:
                learned[transaction.merchant_clean] = transaction.true_category
                answered += 1
        corrected = sum(
            prediction.category == transaction.true_category
            for prediction, transaction in zip(predictions, transactions)
        )
        accuracy = corrected / len(transactions)
        question_count = sum(
            prediction.confidence_score < 0.50
            for prediction in predictions
        )
        print(f"Week {week}: questions={question_count}, accuracy={accuracy:.4f}, answers={answered}")


if __name__ == "__main__":
    main()
