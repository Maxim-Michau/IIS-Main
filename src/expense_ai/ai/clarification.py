"""Mixed-initiative clarification decisions."""

from datetime import datetime
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.storage.database import questions_table, transactions_table
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

    def rank_pending(self) -> list[dict[str, object]]:
        """Rank pending questions by transaction amount and uncertainty."""
        with Session(self.engine) as session:
            rows = session.execute(select(questions_table).where(
                questions_table.c.status == "PENDING"
            ).order_by(questions_table.c.created_at.desc())).mappings().all()
            transactions = {
                row["id"]: dict(row)
                for row in session.execute(select(transactions_table)).mappings()
            }
        ranked = []
        for row in rows:
            transaction = transactions.get(row["transaction_id"])
            amount = float(transaction["amount"] if transaction else 0.0)
            ranked.append({
                **dict(row),
                "_priority": amount,
            })
        return sorted(ranked, key=lambda row: row["_priority"], reverse=True)

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

    def recurring_question(self, transaction: Transaction) -> None:
        """Ask whether a merchant repeat is a recurring payment."""
        with Session(self.engine) as session:
            rows = session.execute(select(transactions_table).where(
                transactions_table.c.merchant_clean == transaction.merchant_clean
            )).mappings().all()
        if len(rows) >= 2:
            self._create_question(
                transaction, "RECURRING",
                f"You have paid {transaction.merchant_clean} repeatedly. Is it recurring?",
                ["Yes", "No"],
            )

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
            if question_type == "CATEGORY":
                answered_merchants = session.execute(select(transactions_table.c.id).where(
                    transactions_table.c.merchant_clean == transaction.merchant_clean,
                    transactions_table.c.status.in_(["CONFIRMED", "CORRECTED"]),
                )).all()
                if answered_merchants:
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
            row = session.execute(
                select(questions_table).where(questions_table.c.id == question_id)
            ).mappings().first()
            session.execute(update(questions_table).where(
                questions_table.c.id == question_id
            ).values(status="ANSWERED", answer=answer, answered_at=datetime.now()))
            if row:
                transaction_row = session.execute(
                    select(transactions_table).where(
                        transactions_table.c.id == row["transaction_id"]
                    )
                ).mappings().first()
                if transaction_row:
                    session.execute(update(transactions_table).where(
                        transactions_table.c.id == row["transaction_id"]
                    ).values(category=answer, status="CONFIRMED"))
            session.commit()
