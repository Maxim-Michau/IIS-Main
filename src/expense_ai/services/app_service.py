"""Application facade used by the Streamlit UI."""

from datetime import datetime
from typing import Iterable
from sqlalchemy.engine import Engine
from expense_ai.models.transaction import Transaction
from expense_ai.storage.repository import TransactionRepository
from expense_ai.ai.pipeline import CategorisationPipeline
from sqlalchemy import select, delete, insert
from sqlalchemy.orm import Session
from expense_ai.storage.database import (
    activity_log_table, questions_table, budgets_table, insights_table,
    transactions_table,
)


class AppService:
    """Coordinate transaction ingestion and application queries."""

    def __init__(self, engine: Engine, pipeline: CategorisationPipeline) -> None:
        """Initialise service dependencies."""
        self.repository = TransactionRepository(engine)
        self.pipeline = pipeline
        from expense_ai.ai.clarification import ClarificationEngine
        self.clarification = ClarificationEngine(engine)
        from expense_ai.ai.categorisers.rule import RuleCategoriser
        from expense_ai.ai.categorisers.context import ContextCategoriser
        from expense_ai.ai.categorisers.fuzzy import FuzzyMerchantCategoriser
        from expense_ai.ai.categorisers.recurrence import RecurrenceDetector
        for categoriser in self.pipeline.categorisers:
            if isinstance(categoriser, (
                RuleCategoriser, ContextCategoriser, FuzzyMerchantCategoriser,
                RecurrenceDetector,
            )):
                categoriser.engine = engine
        self.clarification.release_questions()

    def configure_clarification(self, auto_threshold: float, ask_threshold: float,
                                max_questions_per_day: int) -> None:
        """Apply live thresholds to subsequent ingestion."""
        self.clarification.auto_threshold = auto_threshold
        self.clarification.ask_threshold = ask_threshold
        self.clarification.max_questions_per_day = max_questions_per_day

    def ingest(
        self, transaction: Transaction, release_questions: bool = True
    ) -> Transaction:
        """Categorise, clarify and persist one transaction."""
        prediction, options = self.pipeline.categorise_with_options(transaction)
        transaction.category = prediction.category
        transaction.confidence_score = prediction.confidence_score
        transaction.explanation = prediction.explanation
        transaction.method = prediction.method
        transaction.true_category = None
        saved = self.repository.add(transaction)
        clarification = self.clarification
        clarification.decide(saved, prediction, options, release=False)
        clarification.location_question(saved)
        clarification.extra_info_question(saved)
        clarification.recurring_question(saved)
        saved = self.repository.update(saved)
        if release_questions:
            clarification.release_questions()
        self.log_activity(
            saved.id,
            "AI_DECISION",
            f"Categorised {saved.merchant_clean} as {saved.category}.",
            method=saved.method,
            confidence=saved.confidence_score,
            explanation=saved.explanation,
        )
        return saved

    def ingest_all(self, transactions: Iterable[Transaction]) -> list[Transaction]:
        """Ingest a collection of transactions."""
        ingested = [
            self.ingest(transaction, release_questions=False)
            for transaction in transactions
        ]
        self.train_ml_if_ready()
        self.clarification.release_questions()
        return ingested

    def get_transactions(self, limit: int | None = None) -> list[Transaction]:
        """List stored transactions."""
        return self.repository.list(limit)

    def get_pending_questions(self) -> list[object]:
        """Return simulated inbox questions."""
        with Session(self.repository.engine) as session:
            return [dict(row) for row in session.execute(
                select(questions_table).where(questions_table.c.status == "PENDING")
            ).mappings().all()]

    def get_queued_question_count(self) -> int:
        """Return the number of questions waiting to be surfaced."""
        from sqlalchemy import func

        with Session(self.repository.engine) as session:
            return int(session.execute(
                select(func.count()).select_from(questions_table).where(
                    questions_table.c.status == "QUEUED"
                )
            ).scalar_one())

    def release_next_question_batch(self) -> int:
        """Release one demo batch without applying questions already surfaced today."""
        return self.clarification.release_questions(ignore_daily_cap=True)

    def save_budget(self, category: str, monthly_limit: float, month: str) -> None:
        """Create or replace a category budget for a calendar month."""
        with Session(self.repository.engine) as session:
            existing = session.execute(select(budgets_table).where(
                budgets_table.c.category == category,
                budgets_table.c.month == month,
            ).limit(1)).first()
            if existing:
                session.execute(budgets_table.update().where(
                    budgets_table.c.category == category,
                    budgets_table.c.month == month,
                ).values(monthly_limit=monthly_limit))
            else:
                session.execute(insert(budgets_table).values(
                    category=category,
                    monthly_limit=monthly_limit,
                    month=month,
                ))
            session.commit()

    def get_budgets(self, month: str) -> dict[str, float]:
        """Return recurring defaults overridden by budgets for the requested month."""
        with Session(self.repository.engine) as session:
            rows = session.execute(select(budgets_table).where(
                budgets_table.c.month.in_(("default", month))
            )).mappings().all()
        budgets = {
            row["category"]: float(row["monthly_limit"])
            for row in rows if row["month"] == "default"
        }
        budgets.update({
            row["category"]: float(row["monthly_limit"])
            for row in rows if row["month"] == month
        })
        return budgets

    def get_pending_insights(self) -> list[dict[str, object]]:
        """Return insight cards awaiting Accept or Dismiss."""
        with Session(self.repository.engine) as session:
            rows = session.execute(select(insights_table).where(
                insights_table.c.status == "PENDING"
            )).mappings().all()
        return [dict(row) for row in rows]

    def answer_question(self, question_id: int, answer: str) -> str | None:
        """Apply one answer to all pending questions of that type for the merchant."""
        from expense_ai.ai.feedback import FeedbackLearner
        from sqlalchemy import select
        with Session(self.repository.engine) as session:
            question = session.execute(
                select(questions_table).where(
                    questions_table.c.id == question_id,
                    questions_table.c.status == "PENDING",
                )
            ).mappings().first()
            if question is None:
                return None
            transaction_row = session.execute(
                select(transactions_table).where(
                    transactions_table.c.id == question["transaction_id"]
                )
            ).mappings().first()
            if transaction_row is None:
                return None
            merchant_questions = session.execute(
                select(questions_table.c.id, questions_table.c.transaction_id)
                .join(
                    transactions_table,
                    questions_table.c.transaction_id == transactions_table.c.id,
                )
                .where(
                    questions_table.c.question_type == question["question_type"],
                    questions_table.c.status == "PENDING",
                    transactions_table.c.merchant_clean == transaction_row["merchant_clean"],
                )
            ).all()
        transaction = self.repository.get(question["transaction_id"])
        if transaction is None:
            return None
        transactions = [
            item for _, transaction_id in merchant_questions
            if (item := self.repository.get(transaction_id)) is not None
        ]
        question_ids = [question_id for question_id, _ in merchant_questions]
        predicted = transaction.category if transaction else "Other"
        promoted = False
        for pending_question_id in question_ids:
            self.clarification.answer_question(pending_question_id, answer)
        if question["question_type"] == "CATEGORY" and transaction:
            promoted = FeedbackLearner(self.repository.engine).record_answer(
                transaction, predicted, answer
            )
            self.repository.update(transaction)
        count = len(transactions)
        merchant = transaction.merchant_clean if transaction else "Merchant"
        question_type = question["question_type"]
        if question_type == "CATEGORY":
            message = (
                f"Learned: {merchant} = {answer}. {count - 1} more {merchant} "
                "payments updated."
                if promoted
                else f"Set {merchant} to {answer} for {count} transactions."
            )
        elif question_type == "LOCATION":
            message = f"{merchant} location set to {answer} for {count} transactions."
        elif question_type == "RECURRING":
            message = f"{merchant} recurring status set to {answer} for {count} transactions."
        else:
            message = f"Saved a note for {merchant} on {count} transactions."
        for item in transactions:
            self.log_activity(
                item.id,
                "ANSWER",
                message,
                method=item.method,
                confidence=item.confidence_score,
                explanation=item.explanation,
            )
        return message

    def log_activity(
        self,
        transaction_id: int | None,
        event_type: str,
        message: str,
        method: str | None = None,
        confidence: float | None = None,
        explanation: str | None = None,
    ) -> None:
        """Persist a user-visible AI decision or data change."""
        if transaction_id is None:
            return
        with Session(self.repository.engine) as session:
            session.execute(activity_log_table.insert().values(
                transaction_id=transaction_id,
                event_type=event_type,
                message=message,
                method=method,
                confidence=confidence,
                explanation=explanation,
                created_at=datetime.now(),
            ))
            session.commit()

    def get_activity_log(
        self, transaction_id: int | None = None, limit: int = 100
    ) -> list[dict[str, object]]:
        """Return recent activity, optionally for one transaction."""
        statement = select(activity_log_table).order_by(
            activity_log_table.c.created_at.desc()
        )
        if transaction_id is not None:
            statement = statement.where(
                activity_log_table.c.transaction_id == transaction_id
            )
        with Session(self.repository.engine) as session:
            rows = session.execute(statement.limit(limit)).mappings().all()
        return [dict(row) for row in rows]

    def train_ml_if_ready(self) -> bool:
        """Train the service ML categoriser once enough labelled rows exist."""
        from expense_ai.ai.categorisers.ml import MLCategoriser
        ml = next((item for item in self.pipeline.categorisers
                   if item.__class__.__name__ == "MLCategoriser"), None)
        if ml is None:
            ml = MLCategoriser()
            self.pipeline.categorisers.append(ml)
        labelled: list[Transaction] = []
        with Session(self.repository.engine) as session:
            from expense_ai.storage.database import feedback_table
            feedback = session.execute(select(feedback_table)).mappings().all()
        for row in feedback:
            transaction = self.repository.get(row["transaction_id"])
            if transaction:
                transaction.category = row["chosen_category"]
                labelled.append(transaction)
        for item in self.get_transactions():
            if item.method == "RULE" and item.confidence_score >= 0.85:
                labelled.append(item)
        labelled = [item for item in labelled if item.category != "Other"]
        if len(labelled) < 10 or len({item.category for item in labelled}) < 2:
            return False
        category_counts = {}
        for item in labelled:
            category_counts[item.category] = category_counts.get(item.category, 0) + 1
        if min(category_counts.values()) < 2:
            return False
        ml.train(
            [item.merchant_clean or item.merchant_raw for item in labelled],
            [item.category for item in labelled],
            [item.amount for item in labelled],
            [item.timestamp.hour for item in labelled],
        )
        if ml not in self.pipeline.categorisers:
            self.pipeline.categorisers.append(ml)
        return True
