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
        """Categorise and persist one transaction."""
        prediction = self.pipeline.categorise(transaction)
        transaction.category = prediction.category
        transaction.confidence_score = prediction.confidence_score
        transaction.explanation = prediction.explanation
        transaction.method = prediction.method
        return self.repository.add(transaction)

    def ingest_all(self, transactions: Iterable[Transaction]) -> list[Transaction]:
        """Ingest a collection of transactions."""
        return [self.ingest(transaction) for transaction in transactions]

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
        ClarificationEngine(self.repository.engine).answer_question(question_id, answer)
