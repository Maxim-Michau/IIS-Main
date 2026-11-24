"""Application facade used by the Streamlit UI."""

from typing import Iterable
from sqlalchemy.engine import Engine
from expense_ai.models.transaction import Transaction
from expense_ai.storage.repository import TransactionRepository
from expense_ai.ai.pipeline import CategorisationPipeline
from sqlalchemy import select, delete, insert
from sqlalchemy.orm import Session
from expense_ai.storage.database import questions_table, budgets_table, insights_table


class AppService:
    """Coordinate transaction ingestion and application queries."""

    def __init__(self, engine: Engine, pipeline: CategorisationPipeline) -> None:
        """Initialise service dependencies."""
        self.repository = TransactionRepository(engine)
        self.pipeline = pipeline
        from expense_ai.ai.clarification import ClarificationEngine
        self.clarification = ClarificationEngine(engine)

    def configure_clarification(self, auto_threshold: float, ask_threshold: float,
                                max_questions_per_day: int) -> None:
        """Apply live thresholds to subsequent ingestion."""
        self.clarification.auto_threshold = auto_threshold
        self.clarification.ask_threshold = ask_threshold
        self.clarification.max_questions_per_day = max_questions_per_day

    def ingest(self, transaction: Transaction) -> Transaction:
        """Categorise, clarify and persist one transaction."""
        prediction = self.pipeline.categorise(transaction)
        transaction.category = prediction.category
        transaction.confidence_score = prediction.confidence_score
        transaction.explanation = prediction.explanation
        transaction.method = prediction.method
        transaction.true_category = None
        saved = self.repository.add(transaction)
        clarification = self.clarification
        clarification.decide(saved, prediction)
        clarification.location_question(saved)
        clarification.extra_info_question(saved)
        clarification.recurring_question(saved)
        return self.repository.update(saved)

    def ingest_all(self, transactions: Iterable[Transaction]) -> list[Transaction]:
        """Ingest a collection of transactions."""
        ingested = [self.ingest(transaction) for transaction in transactions]
        self.train_ml_if_ready()
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
        """Return budgets configured for a calendar month."""
        with Session(self.repository.engine) as session:
            rows = session.execute(select(budgets_table).where(
                budgets_table.c.month == month
            )).mappings().all()
        return {row["category"]: float(row["monthly_limit"]) for row in rows}

    def get_pending_insights(self) -> list[dict[str, object]]:
        """Return insight cards awaiting Accept or Dismiss."""
        with Session(self.repository.engine) as session:
            rows = session.execute(select(insights_table).where(
                insights_table.c.status == "PENDING"
            )).mappings().all()
        return [dict(row) for row in rows]

    def answer_question(self, question_id: int, answer: str) -> None:
        """Answer a pending clarification question."""
        from expense_ai.ai.clarification import ClarificationEngine
        from expense_ai.ai.feedback import FeedbackLearner
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from expense_ai.storage.database import questions_table
        with Session(self.repository.engine) as session:
            question = session.execute(
                select(questions_table).where(questions_table.c.id == question_id)
            ).mappings().first()
        transaction = None
        predicted = "Other"
        if question:
            transaction = self.repository.get(question["transaction_id"])
            predicted = transaction.category if transaction else "Other"
        ClarificationEngine(self.repository.engine).answer_question(question_id, answer)
        if transaction:
            FeedbackLearner(self.repository.engine).record_answer(
                transaction, predicted, answer
            )
            self.repository.update(transaction)

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
