"""Keyword rule categoriser."""

import json
from pathlib import Path
import re
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.ai.categorisers.base import Categoriser
from expense_ai.storage.database import merchant_rules_table


class RuleCategoriser(Categoriser):
    """Match merchant text against default and learned rules."""

    def __init__(self, rules_path: str | Path | None = None,
                 engine: Engine | None = None) -> None:
        """Load default rules and optionally connect to learned merchant rules."""
        path = rules_path or Path(__file__).resolve().parents[4] / "config" / "default_rules.json"
        self.rules = json.loads(Path(path).read_text())
        self.engine = engine

    def categorise(self, transaction: Transaction) -> Prediction:
        """Return a confident rule prediction when a pattern matches."""
        merchant = (transaction.merchant_clean or transaction.merchant_raw).lower()
        learned_rules = self._learned_rules()
        for pattern, category, confirmations in learned_rules:
            if self._matches(merchant, pattern):
                return Prediction(
                    category,
                    0.98,
                    f"You labelled this merchant {confirmations} times.",
                    "LEARNED",
                )
        for pattern, category in sorted(self.rules.items(), key=lambda item: len(item[0]), reverse=True):
            if self._matches(merchant, pattern):
                return Prediction(category, 0.95, f"Merchant matches the '{pattern}' rule.", "RULE")
        return Prediction("Other", 0.20, "No merchant rule matched.", "RULE")

    def _learned_rules(self) -> list[tuple[str, str, int]]:
        """Read promoted rules each time so new feedback is immediately available."""
        if self.engine is None:
            return []
        with Session(self.engine) as session:
            rows = session.execute(
                select(merchant_rules_table).order_by(
                    merchant_rules_table.c.times_confirmed.desc(),
                    merchant_rules_table.c.pattern,
                )
            ).mappings().all()
        return [
            (row["pattern"].lower(), row["category"], row["times_confirmed"])
            for row in rows
        ]

    @staticmethod
    def _matches(merchant: str, pattern: str) -> bool:
        """Match longer rules as merchant words and short rules exactly."""
        normalised_pattern = re.escape(pattern.lower())
        if len(pattern) >= 4:
            return re.search(rf"\b{normalised_pattern}\b", merchant) is not None
        return merchant == pattern.lower()
