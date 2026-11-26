"""Generate a synthetic expense-ai demonstration database."""

import argparse
from itertools import groupby
import logging

from expense_ai.services.app_service import AppService
from expense_ai.services.pipeline_factory import build_pipeline
from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.storage.database import create_database
from expense_ai.storage.repository import TransactionRepository


logger = logging.getLogger(__name__)


def generate_data(reset: bool = False) -> int:
    """Generate synthetic transactions and return the number stored."""
    engine = create_database()
    if TransactionRepository(engine).list(limit=1):
        if not reset:
            raise ValueError(
                "Database already contains transactions; pass --reset to replace them."
            )
        service = AppService(engine, build_pipeline())
        service.reset_demo_data()
    service = AppService(engine, build_pipeline())

    transactions = sorted(
        SyntheticBankSource().fetch_transactions(),
        key=lambda transaction: transaction.timestamp,
    )
    total = len(transactions)
    logger.info("Generating %d synthetic transactions.", total)
    ingested_count = 0
    for _, day_transactions in groupby(
        transactions, key=lambda transaction: transaction.timestamp.date()
    ):
        batch = list(day_transactions)
        service.ingest_all(batch)
        ingested_count += len(batch)
        logger.info("Ingested %d/%d transactions.", ingested_count, total)
    logger.info("Synthetic transaction generation complete.")
    return ingested_count


def main() -> None:
    """Parse command-line options and generate demo data."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear all existing demo data before generating transactions.",
    )
    args = parser.parse_args()
    try:
        generate_data(reset=args.reset)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
