"""Detect recurring payment patterns."""

from dataclasses import dataclass
from statistics import median
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from expense_ai.ai.categorisers.base import Categoriser
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.storage.database import transactions_table
from config.settings import (
    RECURRENCE_AMOUNT_TOLERANCE,
    RECURRENCE_GAP_TOLERANCE_DAYS,
    RECURRENCE_MIN_REGULARITY,
    RECURRENCE_SUGGESTION_CONFIDENCE,
)


@dataclass(frozen=True)
class RecurrenceResult:
    is_recurring: bool
    interval: str | None
    typical_amount: float | None
    count: int
    borderline: bool = False


class RecurrenceDetector(Categoriser):
    """Detect regular merchant payments and suggest subscriptions."""

    INTERVALS = ((7, "weekly"), (14, "fortnightly"), (30, "monthly"))

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine

    def detect(
        self,
        transaction: Transaction,
        transactions: Iterable[Transaction] | None = None,
    ) -> RecurrenceResult:
        history = list(transactions) if transactions is not None else self._merchant_history(transaction)
        matching = [item for item in history if item.merchant_clean == transaction.merchant_clean]
        if transaction not in matching:
            matching.append(transaction)
        matching.sort(key=lambda item: item.timestamp)
        count = len(matching)
        if count < 3:
            return RecurrenceResult(False, None, None, count)

        amounts = [item.amount for item in matching]
        typical_amount = float(median(amounts))
        amounts_regular = sum(
            abs(amount - typical_amount) <= typical_amount * RECURRENCE_AMOUNT_TOLERANCE
            for amount in amounts
        ) / count >= RECURRENCE_MIN_REGULARITY
        gaps = [
            (right.timestamp.date() - left.timestamp.date()).days
            for left, right in zip(matching, matching[1:])
        ]
        median_gap = float(median(gaps))
        nearest = min(self.INTERVALS, key=lambda item: abs(item[0] - median_gap))
        days, interval = nearest
        gaps_regular = sum(
            abs(gap - days) <= RECURRENCE_GAP_TOLERANCE_DAYS for gap in gaps
        ) / len(gaps) >= RECURRENCE_MIN_REGULARITY
        borderline = (
            amounts_regular
            and abs(median_gap - days) <= RECURRENCE_GAP_TOLERANCE_DAYS * 2
            and not gaps_regular
        )
        return RecurrenceResult(
            amounts_regular and gaps_regular,
            interval if amounts_regular and (gaps_regular or borderline) else None,
            round(typical_amount, 2),
            count,
            borderline,
        )

    def categorise(self, transaction: Transaction) -> Prediction:
        result = self.detect(transaction)
        transaction.is_recurring = result.is_recurring
        if result.is_recurring:
            return Prediction(
                "Subscriptions",
                RECURRENCE_SUGGESTION_CONFIDENCE,
                f"{result.count} similar payments occur about every {result.interval}.",
                "RECURRENCE",
            )
        return Prediction("Other", 0.20, "No regular payment pattern detected.", "RECURRENCE")

    def _merchant_history(self, transaction: Transaction) -> list[Transaction]:
        if self.engine is None:
            return [transaction]
        with Session(self.engine) as session:
            rows = session.execute(
                select(transactions_table).where(
                    transactions_table.c.merchant_clean == transaction.merchant_clean
                )
            ).mappings().all()
        return [Transaction(**dict(row)) for row in rows]
