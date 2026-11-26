"""Categorisation cascade and confidence aggregation."""

from expense_ai.ai.categorisers.base import Categoriser
from expense_ai.ai.categorisers.llm import LLMCategoriser
from expense_ai.models.transaction import Prediction, Transaction
from config.settings import (
    ASK_THRESHOLD,
    CONFLICT_CONFIDENCE_CAP,
    STRONG_METHOD_THRESHOLD,
    SUPPORTING_CONFIDENCE_ADJUSTMENT,
)


LABEL_METHOD_ORDER = ("LEARNED", "RULE", "FUZZY", "ML", "LLM")
LABEL_METHODS = frozenset(LABEL_METHOD_ORDER)
SUPPORTING_METHODS = frozenset({"CONTEXT", "RECURRENCE"})


class CategorisationPipeline:
    """Run label sources in cascade order and treat context as supporting evidence."""

    def __init__(
        self,
        categorisers: list[Categoriser],
        ask_threshold: float = ASK_THRESHOLD,
    ) -> None:
        """Inject categorisers and the threshold for optional LLM fallback."""
        self.categorisers = categorisers
        self.ask_threshold = ask_threshold
        self._llm_cache: dict[str, Prediction] = {}

    def categorise(self, transaction: Transaction) -> Prediction:
        """Return the strongest label-source prediction."""
        return self.categorise_with_options(transaction)[0]

    def categorise_with_options(
        self, transaction: Transaction
    ) -> tuple[Prediction, list[str]]:
        """Evaluate label sources and bounded supporting signals."""
        predictions: list[Prediction] = []
        supporting: list[Prediction] = []
        llm_categorisers: list[LLMCategoriser] = []
        for categoriser in self.categorisers:
            if isinstance(categoriser, LLMCategoriser):
                llm_categorisers.append(categoriser)
                continue
            prediction = categoriser.categorise(transaction)
            predictions.append(prediction)
            if prediction.method in SUPPORTING_METHODS:
                supporting.append(prediction)

        label_predictions = [
            prediction for prediction in predictions
            if prediction.method not in SUPPORTING_METHODS
        ]
        best = self._select_label(label_predictions)
        if best is None:
            best = self._select_fallback(supporting, label_predictions)
        elif supporting:
            best = self._apply_support(best, supporting)

        if (
            best.confidence_score < self.ask_threshold
            and llm_categorisers
            and any(categoriser.enabled for categoriser in llm_categorisers)
        ):
            llm_prediction = self._cached_llm_prediction(
                llm_categorisers[0], transaction
            )
            predictions.append(llm_prediction)
            label_predictions.append(llm_prediction)
            if llm_prediction.category != "Other" and (
                best.category == "Other"
                or llm_prediction.confidence_score > best.confidence_score
            ):
                best = llm_prediction

        best = self._apply_conflict_cap(best, label_predictions)
        suggestions: list[str] = []
        for prediction in sorted(
            predictions, key=lambda item: item.confidence_score, reverse=True
        ):
            if prediction.category != "Other" and prediction.category not in suggestions:
                suggestions.append(prediction.category)
            if len(suggestions) == 3:
                break
        return best, suggestions or ["Other"]

    def _cached_llm_prediction(
        self, categoriser: LLMCategoriser, transaction: Transaction
    ) -> Prediction:
        """Call the enabled LLM once per normalised merchant."""
        merchant = transaction.merchant_clean or transaction.merchant_raw
        cache_key = " ".join(merchant.casefold().split())
        if cache_key not in self._llm_cache:
            self._llm_cache[cache_key] = categoriser.categorise(transaction)
        return self._llm_cache[cache_key]

    @staticmethod
    def _select_label(predictions: list[Prediction]) -> Prediction | None:
        """Select a confident label by cascade order, then by confidence."""
        labels = [item for item in predictions if item.category != "Other"]
        if not labels:
            return None
        for method in LABEL_METHOD_ORDER:
            confident = next(
                (
                    item for item in labels
                    if item.method == method
                    and item.confidence_score >= STRONG_METHOD_THRESHOLD
                ),
                None,
            )
            if confident:
                return confident
        priorities = {method: index for index, method in enumerate(LABEL_METHOD_ORDER)}
        return max(
            labels,
            key=lambda item: (
                item.confidence_score,
                -priorities.get(item.method, len(priorities)),
            ),
        )

    @staticmethod
    def _select_fallback(
        supporting: list[Prediction], labels: list[Prediction]
    ) -> Prediction:
        """Use recurrence or context only when no label source matched."""
        recurrence = next(
            (
                item for item in supporting
                if item.method == "RECURRENCE" and item.category != "Other"
            ),
            None,
        )
        if recurrence:
            return recurrence
        context = next(
            (
                item for item in supporting
                if item.method == "CONTEXT" and item.category != "Other"
            ),
            None,
        )
        if context:
            return context
        candidates = labels + supporting
        return max(
            candidates,
            key=lambda item: item.confidence_score,
            default=Prediction(
                "Other", 0.20, "No categorisers are configured.", "CONTEXT"
            ),
        )

    @staticmethod
    def _apply_support(
        best: Prediction, supporting: list[Prediction]
    ) -> Prediction:
        """Let supporting signals nudge a label without creating conflicts."""
        signals = [item for item in supporting if item.category != "Other"]
        if not signals:
            return best
        matching = any(
            item.category == best.category and item.category != "Other"
            for item in signals
        )
        adjustment = (
            SUPPORTING_CONFIDENCE_ADJUSTMENT
            if matching else -SUPPORTING_CONFIDENCE_ADJUSTMENT
        )
        return Prediction(
            best.category,
            min(1.0, max(0.0, best.confidence_score + adjustment)),
            best.explanation,
            best.method,
        )

    @staticmethod
    def _apply_conflict_cap(
        best: Prediction, predictions: list[Prediction]
    ) -> Prediction:
        """Cap confidence only when independent label sources disagree."""
        strong_categories = {
            item.category for item in predictions
            if item.method in LABEL_METHODS
            and item.category != "Other"
            and item.confidence_score >= STRONG_METHOD_THRESHOLD
        }
        if len(strong_categories) <= 1:
            return best
        conflict = next(
            item for item in predictions
            if item.method in LABEL_METHODS
            and item.category != best.category
            and item.confidence_score >= STRONG_METHOD_THRESHOLD
        )
        return Prediction(
            best.category,
            min(best.confidence_score, CONFLICT_CONFIDENCE_CAP),
            f"Strong methods disagree: {best.method} predicts {best.category}, "
            f"while {conflict.method} predicts {conflict.category}.",
            best.method,
        )
