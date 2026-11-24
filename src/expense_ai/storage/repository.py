"""All transaction and application database operations."""

from typing import Optional
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine

from expense_ai.models.transaction import Transaction
from expense_ai.storage.database import transactions_table


class TransactionRepository:
    """Persist and retrieve transactions."""

    def __init__(self, engine: Engine) -> None:
        """Initialise the repository."""
        self.engine = engine

    def add(self, transaction: Transaction) -> Transaction:
        """Insert a transaction and return it with an ID."""
        values = vars(transaction).copy()
        values.pop("id", None)
        with Session(self.engine) as session:
            result = session.execute(transactions_table.insert().values(values))
            session.commit()
            transaction.id = int(result.inserted_primary_key[0])
        return transaction

    def get(self, transaction_id: int) -> Optional[Transaction]:
        """Get a transaction by ID."""
        with Session(self.engine) as session:
            row = session.execute(
                select(transactions_table).where(transactions_table.c.id == transaction_id)
            ).mappings().first()
        return self._to_model(row) if row else None

    def list(self, limit: Optional[int] = None) -> list[Transaction]:
        """List transactions newest first."""
        statement = select(transactions_table).order_by(transactions_table.c.timestamp.desc())
        if limit:
            statement = statement.limit(limit)
        with Session(self.engine) as session:
            rows = session.execute(statement).mappings().all()
        return [self._to_model(row) for row in rows]

    def update(self, transaction: Transaction) -> Transaction:
        """Update an existing transaction."""
        if transaction.id is None:
            raise ValueError("Transaction must have an ID")
        values = vars(transaction).copy()
        values.pop("id")
        with Session(self.engine) as session:
            session.execute(
                transactions_table.update().where(transactions_table.c.id == transaction.id).values(values)
            )
            session.commit()
        return transaction

    def delete(self, transaction_id: int) -> bool:
        """Delete a transaction."""
        with Session(self.engine) as session:
            result = session.execute(delete(transactions_table).where(transactions_table.c.id == transaction_id))
            session.commit()
        return result.rowcount > 0

    @staticmethod
    def _to_model(row: object) -> Transaction:
        """Convert a database mapping into a model."""
        return Transaction(**dict(row))
