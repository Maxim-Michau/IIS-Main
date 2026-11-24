"""Mixed-initiative clarification decisions."""

from datetime import date, datetime
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.storage.database import questions_table
from config.settings import (AUTO_ACCEPT_THRESHOLD, ASK_THRESHOLD,
                             MAX_QUESTIONS_PER_DAY)


class ClarificationEngine:
    """Decide whether to act, ask, or confirm tentatively."""

    def __init__(self, engine: Engine, auto_threshold: float = AUTO_ACCEPT_THRESHOLD,
                 ask_threshold: float = ASK_THRESHOLD,
                 max_questions_per_day: int = MAX_QUESTIONS_PER_DAY) -> None:
        """Configure thresholds and interruption limit."""
        self.engine = engine
        self.auto_threshold = auto_threshold
        self.ask_threshold = ask_threshold
        self.max_questions_per_day = max_questions_per_day

    def decide(self, transaction: Transaction, prediction: Prediction,
               options: list[str] | None = None) -> str:
        """Apply confidence thresholds and persist a category question."""
        if prediction.confidence_score >= self.auto_threshold:
            transaction.status = "AUTO"
            return "AUTO"
        if prediction.confidence_score >= self.ask_threshold:
            transaction.status = "TENTATIVE"
            self._create_question(transaction, "CATEGORY",
                                  f"Is {transaction.merchant_clean} {prediction.category}?",
                                  options or [prediction.category])
            return "TENTATIVE"
        transaction.status = "TENTATIVE"
        top_options = options or [prediction.category, "Other"]
        self._create_question(transaction, "CATEGORY",
                              f"What category is this £{transaction.amount:.2f} payment?",
                              top_options + ["Other"] if "Other" not in top_options else top_options)
        return "ASK"

    def location_question(self, transaction: Transaction) -> None:
        """Create a location question for missing or unusual locations."""
        if transaction.location is None:
            self._create_question(transaction, "LOCATION",
                                  f"Where was this £{transaction.amount:.2f} payment?",
                                  ["Birmingham", "Manchester", "Another location"])
        elif transaction.location not in ("Birmingham", "Coventry", "Solihull"):
            self._create_question(transaction, "LOCATION",
                                  f"You spent £{transaction.amount:.2f} in {transaction.location}. Were you travelling?",
                                  ["Yes", "No"])

    def extra_info_question(self, transaction: Transaction) -> None:
        """Ask about unusually large or unrecognised transactions."""
        if transaction.amount >= 100.0:
            self._create_question(transaction, "EXTRA_INFO",
                                  f"What was this £{transaction.amount:.2f} for? Is it one-off or recurring?",
                                  ["One-off", "Recurring"])

    def daily_pending_count(self) -> int:
        """Count pending questions for today."""
        today = datetime.now().date()
        with Session(self.engine) as session:
            rows = session.execute(select(questions_table)).mappings().all()
        return sum(1 for row in rows if row["status"] == "PENDING"
                   and getattr(row["created_at"], "date", lambda: today)() == today)

    def _create_question(self, transaction: Transaction, question_type: str,
                         prompt: str, options: list[str]) -> None:
        """Persist a question unless the daily cap is reached or it is duplicate."""
        if self.daily_pending_count() >= self.max_questions_per_day:
            return
        with Session(self.engine) as session:
            duplicate = session.execute(select(questions_table).where(
                questions_table.c.transaction_id == transaction.id,
                questions_table.c.question_type == question_type,
                questions_table.c.status == "PENDING",
            )).first()
            if duplicate:
                return
            session.execute(insert(questions_table).values(
                transaction_id=transaction.id, question_type=question_type,
                prompt_text=prompt, options="|".join(options), status="PENDING",
                created_at=datetime.now(),
            ))
            session.commit()

    def answer_question(self, question_id: int, answer: str) -> None:
        """Record a pending question answer."""
        with Session(self.engine) as session:
            session.execute(update(questions_table).where(
                questions_table.c.id == question_id
            ).values(status="ANSWERED", answer=answer, answered_at=datetime.now()))
            session.commit()
