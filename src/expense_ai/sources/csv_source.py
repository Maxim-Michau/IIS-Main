"""CSV bank source."""

from pathlib import Path
from typing import Iterable
import pandas as pd
from expense_ai.models.transaction import Transaction
from expense_ai.sources.bank_source import BankSource


class CsvBankSource(BankSource):
    """Load bank transactions from a CSV file."""

    def __init__(self, path: str | Path) -> None:
        """Initialise the source with a CSV path."""
        self.path = Path(path)

    def fetch_transactions(self) -> Iterable[Transaction]:
        """Read transactions from the CSV file."""
        frame = pd.read_csv(self.path)
        for row in frame.to_dict(orient="records"):
            yield Transaction(
                id=None,
                timestamp=pd.Timestamp(row["timestamp"]).to_pydatetime(),
                amount=float(row["amount"]),
                merchant_raw=str(row["merchant_raw"]),
                merchant_clean=str(row.get("merchant_clean", row["merchant_raw"]).lower()),
                location=row.get("location"),
                category="Other",
                true_category=row.get("true_category"),
                source="CSV",
            )
