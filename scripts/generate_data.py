"""Generate a synthetic expense-ai demonstration database."""

from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.storage.database import create_database
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.services.app_service import AppService


def main() -> None:
    """Generate and store synthetic transactions."""
    engine = create_database()
    service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
    ingested = service.ingest_all(SyntheticBankSource().fetch_transactions())
    print("Generated synthetic transactions")


if __name__ == "__main__":
    main()
