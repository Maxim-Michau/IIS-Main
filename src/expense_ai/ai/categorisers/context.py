"""Feature-based categorisation using transaction context and user history."""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from expense_ai.ai.categorisers.base import Categoriser
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.storage.database import transactions_table
from config.settings import (
    CONTEXT_AGREEMENT_CONFIDENCE_MAX,
    CONTEXT_AGREEMENT_CONFIDENCE_RANGE,
    CONTEXT_BASE_CONFIDENCE,
    CONTEXT_HISTORY_CONFIDENCE_MAX,
    CONTEXT_HISTORY_CONFIDENCE_RANGE,
    CONTEXT_MCC_CONFIDENCE,
)


MCC_CATEGORIES = {
    "5411": "Groceries",
    "5812": "Eating Out",
    "5814": "Takeaways",
    "4111": "Transport",
    "4900": "Rent & Bills",
    "5816": "Subscriptions",
    "5942": "Education",
    "7997": "Health & Fitness",
    "5941": "Shopping",
}


class ContextCategoriser(Categoriser):
    """Combine merchant MCC, time, weekday, amount, and location signals."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine
        self._history_cache: list[Transaction] | None = None

    def begin_batch(self) -> None:
        """Cache confirmed history for one ingestion batch."""
        self._history_cache = self._query_confirmed_history()

    def end_batch(self) -> None:
        """Release history cached for the completed ingestion batch."""
        self._history_cache = None

    def categorise(self, transaction: Transaction) -> Prediction:
        mcc_category = MCC_CATEGORIES.get(transaction.mcc or "")
        history = [
            row for row in self._confirmed_history()
            if row.merchant_clean.casefold() == transaction.merchant_clean.casefold()
        ]
        counts = Counter(row.category for row in history)
        history_category, history_count = counts.most_common(1)[0] if counts else (None, 0)
        total = sum(counts.values())
        history_share = history_count / total if total else 0.0
        agrees = bool(mcc_category and history_category == mcc_category)
        if mcc_category and history_category and agrees:
            category = mcc_category
            confidence = min(
                CONTEXT_AGREEMENT_CONFIDENCE_MAX,
                CONTEXT_MCC_CONFIDENCE
                + history_share * CONTEXT_AGREEMENT_CONFIDENCE_RANGE,
            )
            evidence = "merchant history and MCC agree"
        elif mcc_category:
            category = mcc_category
            confidence = CONTEXT_MCC_CONFIDENCE
            evidence = "simulated bank MCC"
        elif history_category:
            category = history_category
            confidence = min(
                CONTEXT_HISTORY_CONFIDENCE_MAX,
                CONTEXT_BASE_CONFIDENCE
                + history_share * CONTEXT_HISTORY_CONFIDENCE_RANGE,
            )
            evidence = "confirmed history for this merchant"
        else:
            return Prediction(
                "Other",
                CONTEXT_BASE_CONFIDENCE,
                "No merchant or MCC evidence matched.",
                "CONTEXT",
            )
        if (
            transaction.mcc in {"5812", "5814"}
            and (transaction.timestamp.hour >= 21 or transaction.timestamp.hour < 5)
        ):
            evidence += ", late-night food purchase"
        return Prediction(category, confidence, f"Context signals: {evidence}.", "CONTEXT")

    def _confirmed_history(self) -> list[Transaction]:
        if self._history_cache is not None:
            return self._history_cache
        return self._query_confirmed_history()

    def _query_confirmed_history(self) -> list[Transaction]:
        if self.engine is None:
            return []
        with Session(self.engine) as session:
            rows = session.execute(
                select(transactions_table).where(
                    transactions_table.c.status.in_(("CONFIRMED", "CORRECTED"))
                )
            ).mappings().all()
        return [Transaction(**dict(row)) for row in rows]
