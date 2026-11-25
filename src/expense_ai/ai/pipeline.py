"""Categorisation pipeline."""

from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.ai.categorisers.base import Categoriser


class CategorisationPipeline:
    """Run categorisers in cascade order and return the strongest prediction."""

    def __init__(self, categorisers: list[Categoriser]) -> None:
        """Inject categorisers in cascade order."""
        self.categorisers = categorisers

    def categorise(self, transaction: Transaction) -> Prediction:
        """Compare all methods and flag strong disagreements for clarification."""
        return self.categorise_with_options(transaction)[0]

    def categorise_with_options(self, transaction: Transaction) -> tuple[Prediction, list[str]]:
        """Return the selected prediction and distinct category suggestions."""
        predictions: list[Prediction] = []
        for categoriser in self.categorisers:
            predictions.append(categoriser.categorise(transaction))
        if not predictions:
            return Prediction(
                "Other", 0.20, "No categorisers are configured.", "CONTEXT"
            ), ["Other"]
        best = max(predictions, key=lambda prediction: prediction.confidence_score)
        strong = [
            prediction for prediction in predictions
            if prediction.confidence_score >= 0.75
        ]
        alternatives = {
            prediction.category: prediction
            for prediction in strong
            if prediction.category != best.category
        }
        if alternatives:
            conflict = max(alternatives.values(), key=lambda item: item.confidence_score)
            best = Prediction(
                best.category,
                min(best.confidence_score, 0.49),
                f"Strong methods disagree: {best.method} predicts {best.category}, "
                f"while {conflict.method} predicts {conflict.category}.",
                best.method,
            )
        suggestions: list[str] = []
        for prediction in sorted(
            predictions, key=lambda item: item.confidence_score, reverse=True
        ):
            if prediction.category != "Other" and prediction.category not in suggestions:
                suggestions.append(prediction.category)
            if len(suggestions) == 3:
                break
        return best, suggestions or ["Other"]
