"""Categorisation pipeline."""

from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.ai.categorisers.base import Categoriser


class CategorisationPipeline:
    """Run categorisers in cascade order and return the strongest prediction."""

    def __init__(self, categorisers: list[Categoriser]) -> None:
        """Inject categorisers in cascade order."""
        self.categorisers = categorisers

    def categorise(self, transaction: Transaction) -> Prediction:
        """Stop after a high-confidence rule match; otherwise choose the highest score."""
        predictions: list[Prediction] = []
        for categoriser in self.categorisers:
            prediction = categoriser.categorise(transaction)
            predictions.append(prediction)
            if prediction.method == "RULE" and prediction.confidence_score >= 0.85:
                return prediction
        return max(predictions, key=lambda prediction: prediction.confidence_score)
