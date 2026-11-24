"""Generate a synthetic expense-ai demonstration database."""

from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.storage.database import create_database
from expense_ai.storage.repository import TransactionRepository


def main() -> None:
    """Generate and store synthetic transactions."""
    engine = create_database()
    repository = TransactionRepository(engine)
    for transaction in SyntheticBankSource().fetch_transactions():
        repository.add(transaction)
    print("Generated synthetic transactions")


if __name__ == "__main__":
    main()
