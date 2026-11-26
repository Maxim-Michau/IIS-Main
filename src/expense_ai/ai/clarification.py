"""Mixed-initiative clarification decisions."""

from datetime import datetime
from typing import Callable
from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.storage.database import questions_table, transactions_table
from config.settings import (AUTO_ACCEPT_THRESHOLD, ASK_THRESHOLD,
                             EXTRA_INFO_MIN_AMOUNT, MAX_QUESTIONS_PER_DAY,
                             QUESTION_TYPE_WEIGHTS)


class ClarificationEngine:
    """Decide whether to act, ask, or confirm tentatively."""

    def __init__(self, engine: Engine, auto_threshold: float = AUTO_ACCEPT_THRESHOLD,
                 ask_threshold: float = ASK_THRESHOLD,
                 max_questions_per_day: int = MAX_QUESTIONS_PER_DAY,
                 clock: Callable[[], datetime] | None = None) -> None:
        """Configure thresholds and interruption limit."""
        self.engine = engine
        self.auto_threshold = auto_threshold
        self.ask_threshold = ask_threshold
        self.max_questions_per_day = max_questions_per_day
        self.clock = clock or datetime.now

    def decide(self, transaction: Transaction, prediction: Prediction,
               options: list[str] | None = None,
               release: bool = True) -> str:
        """Apply confidence thresholds and persist a category question."""
        if prediction.confidence_score >= self.auto_threshold:
            transaction.status = "AUTO"
            return "AUTO"
        if prediction.confidence_score >= self.ask_threshold:
            transaction.status = "TENTATIVE"
            self._create_question(transaction, "CATEGORY",
                                  f"Is {transaction.merchant_clean} {prediction.category}?",
                                  options or [prediction.category])
            if release:
                self.release_questions()
            return "TENTATIVE"
        transaction.status = "TENTATIVE"
        top_options = options or [prediction.category, "Other"]
        self._create_question(transaction, "CATEGORY",
                              f"What category is this £{transaction.amount:.2f} payment?",
                              top_options + ["Other"] if "Other" not in top_options else top_options)
        if release:
            self.release_questions()
        return "ASK"

    def release_questions(
        self, now: datetime | None = None, ignore_daily_cap: bool = False
    ) -> int:
        """Surface queued questions in priority order within the daily cap."""
        current = now or self.clock()
        with Session(self.engine) as session:
            surfaced_today = session.execute(
                select(func.count()).select_from(questions_table).where(
                    questions_table.c.status.in_(("PENDING", "ANSWERED")),
                    func.date(questions_table.c.surfaced_at) == current.date().isoformat(),
                )
            ).scalar_one()
            available = (
                self.max_questions_per_day
                if ignore_daily_cap
                else max(0, self.max_questions_per_day - int(surfaced_today))
            )
            if available == 0:
                return 0
            rows = session.execute(
                select(questions_table, transactions_table.c.amount,
                       transactions_table.c.confidence_score)
                .select_from(questions_table.outerjoin(
                    transactions_table,
                    questions_table.c.transaction_id == transactions_table.c.id,
                ))
                .where(questions_table.c.status == "QUEUED")
            ).mappings().all()
            ranked = self._rank_rows(rows)
            selected = ranked[:available]
            for row in selected:
                session.execute(update(questions_table).where(
                    questions_table.c.id == row["id"],
                    questions_table.c.status == "QUEUED",
                ).values(status="PENDING", surfaced_at=current))
            session.commit()
        return len(selected)

    @staticmethod
    def _rank_rows(rows: object) -> list[dict[str, object]]:
        """Return rows ordered by configured priority and prediction uncertainty."""
        ranked = []
        for result in rows:
            row = dict(result)
            confidence = float(row.get("confidence_score") or 0.0)
            amount = abs(float(row.get("amount") or 0.0))
            weight = QUESTION_TYPE_WEIGHTS.get(row["question_type"], 1.0)
            row["_priority"] = weight * (1.0 - confidence) * amount
            ranked.append(row)
        return sorted(ranked, key=lambda row: row["_priority"], reverse=True)

    def location_question(self, transaction: Transaction) -> None:
        """Create a location question for missing or unusual locations."""
        with Session(self.engine) as session:
            previous_locations = session.execute(
                select(transactions_table.c.location).where(
                    transactions_table.c.merchant_clean == transaction.merchant_clean,
                    transactions_table.c.id != transaction.id,
                    transactions_table.c.location.is_not(None),
                ).distinct()
            ).scalars().all()
        if transaction.location is None or (
            previous_locations and transaction.location not in previous_locations
        ):
            usual = ", ".join(previous_locations)
            prompt = (
                f"Where did this {transaction.merchant_clean} payment happen?"
                if not usual else
                f"This {transaction.merchant_clean} payment is in {transaction.location}; "
                f"previous payments were in {usual}. Is this location correct?"
            )
            self._create_question(
                transaction, "LOCATION", prompt, list(previous_locations),
            )

    def recurring_question(self, transaction: Transaction) -> None:
        """Ask once per merchant only when the observed payment pattern is borderline."""
        from expense_ai.ai.categorisers.recurrence import RecurrenceDetector

        with Session(self.engine) as session:
            rows = session.execute(select(transactions_table).where(
                transactions_table.c.merchant_clean == transaction.merchant_clean
            )).mappings().all()
            existing_question = session.execute(
                select(questions_table.c.id)
                .join(
                    transactions_table,
                    questions_table.c.transaction_id == transactions_table.c.id,
                )
                .where(
                    transactions_table.c.merchant_clean == transaction.merchant_clean,
                    questions_table.c.question_type == "RECURRING",
                )
            ).first()
        result = RecurrenceDetector(self.engine).detect(transaction)
        if result.borderline and not existing_question:
            amounts = [float(row["amount"]) for row in rows]
            low, high = min(amounts), max(amounts)
            days = {"weekly": 7, "fortnightly": 14, "monthly": 30}[result.interval]
            wording = {
                "weekly": "regular weekly payment",
                "fortnightly": "regular fortnightly payment",
                "monthly": "regular monthly payment",
            }[result.interval]
            self._create_question(
                transaction, "RECURRING",
                f"I noticed {result.count} {transaction.merchant_clean} payments of "
                f"GBP {low:.0f}-{high:.0f}, roughly every {days} days. "
                f"Should I treat this as a {wording}?",
                ["Yes", "No"],
            )

    def extra_info_question(self, transaction: Transaction) -> None:
        """Ask about unusually large or unrecognised transactions."""
        if (
            transaction.amount >= EXTRA_INFO_MIN_AMOUNT
            and transaction.category == "Other"
        ):
            self._create_question(transaction, "EXTRA_INFO",
                                  f"What was this £{transaction.amount:.2f} for? Is it one-off or recurring?",
                                  ["One-off", "Recurring"])

    def daily_pending_count(self) -> int:
        """Count pending questions for today."""
        with Session(self.engine) as session:
            return int(session.execute(
                select(func.count()).select_from(questions_table).where(
                    questions_table.c.status == "PENDING",
                    func.date(questions_table.c.surfaced_at)
                    == self.clock().date().isoformat(),
                )
            ).scalar_one())

    def daily_question_count(self) -> int:
        """Count questions created today, independently of surfacing."""
        with Session(self.engine) as session:
            return int(session.execute(
                select(func.count()).select_from(questions_table).where(
                    func.date(questions_table.c.created_at)
                    == self.clock().date().isoformat(),
                )
            ).scalar_one())

    def _create_question(self, transaction: Transaction, question_type: str,
                         prompt: str, options: list[str]) -> None:
        """Persist a queued question unless an equivalent active one exists."""
        with Session(self.engine) as session:
            duplicate = session.execute(select(questions_table).where(
                questions_table.c.transaction_id == transaction.id,
                questions_table.c.question_type == question_type,
                questions_table.c.status.in_(("QUEUED", "PENDING")),
            )).first()
            if duplicate:
                return
            session.execute(insert(questions_table).values(
                transaction_id=transaction.id, question_type=question_type,
                prompt_text=prompt, options="|".join(options), status="QUEUED",
                created_at=self.clock(),
            ))
            session.commit()

    def answer_question(self, question_id: int, answer: str) -> None:
        """Record a pending question answer."""
        with Session(self.engine) as session:
            row = session.execute(
                select(questions_table).where(questions_table.c.id == question_id)
            ).mappings().first()
            session.execute(update(questions_table).where(
                questions_table.c.id == question_id
            ).values(status="ANSWERED", answer=answer, answered_at=self.clock()))
            if row:
                transaction_row = session.execute(
                    select(transactions_table).where(
                        transactions_table.c.id == row["transaction_id"]
                    )
                ).mappings().first()
                if transaction_row:
                    values: dict[str, object] = {}
                    question_type = row["question_type"]
                    if question_type == "CATEGORY":
                        values.update(
                            category=answer,
                            status=("CONFIRMED" if transaction_row["category"] == answer
                                    else "CORRECTED"),
                        )
                    elif question_type == "LOCATION":
                        values["location"] = answer
                    elif question_type == "RECURRING":
                        values["is_recurring"] = answer.strip().casefold() in {
                            "yes", "y", "true", "1", "recurring",
                        }
                    elif question_type == "EXTRA_INFO":
                        values["note"] = answer
                    if values:
                        session.execute(update(transactions_table).where(
                            transactions_table.c.id == row["transaction_id"]
                        ).values(**values))
            session.commit()
