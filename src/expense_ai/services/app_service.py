"""Application facade used by the Streamlit UI."""

from typing import Iterable
from sqlalchemy.engine import Engine
from expense_ai.models.transaction import Transaction
from expense_ai.storage.repository import TransactionRepository
from expense_ai.ai.pipeline import CategorisationPipeline
from sqlalchemy import select
from sqlalchemy.orm import Session
from expense_ai.storage.database import questions_table


class AppService:
    """Coordinate transaction ingestion and application queries."""

    def __init__(self, engine: Engine, pipeline: CategorisationPipeline) -> None:
        """Initialise service dependencies."""
        self.repository = TransactionRepository(engine)
        self.pipeline = pipeline

    def ingest(self, transaction: Transaction) -> Transaction:
        """Categorise, clarify and persist one transaction."""
        prediction = self.pipeline.categorise(transaction)
        transaction.category = prediction.category
        transaction.confidence_score = prediction.confidence_score
        transaction.explanation = prediction.explanation
        transaction.method = prediction.method
        transaction.true_category = None
        saved = self.repository.add(transaction)
        from expense_ai.ai.clarification import ClarificationEngine
        clarification = ClarificationEngine(self.repository.engine)
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
        if ml is not None and ml.is_trained():
            return False
        transactions = [item for item in self.get_transactions()
                        if item.true_category or item.category]
        transactions = [item for item in transactions
                        if item.true_category and item.true_category != "Other"]
        if len(transactions) < 10 or len({item.true_category for item in transactions}) < 2:
            return False
        ml.train(
            [item.merchant_clean or item.merchant_raw for item in transactions],
            [item.true_category for item in transactions],
            [item.amount for item in transactions],
            [item.timestamp.hour for item in transactions],
        )
        return True
