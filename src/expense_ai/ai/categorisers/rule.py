"""Keyword rule categoriser."""

import json
from pathlib import Path
import re
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.ai.categorisers.base import Categoriser


class RuleCategoriser(Categoriser):
    """Match merchant text against default and learned rules."""

    def __init__(self, rules_path: str | Path | None = None) -> None:
        """Load default rules."""
        path = rules_path or Path(__file__).resolve().parents[4] / "config" / "default_rules.json"
        self.rules = json.loads(Path(path).read_text())

    def categorise(self, transaction: Transaction) -> Prediction:
        """Return a confident rule prediction when a pattern matches."""
        merchant = (transaction.merchant_clean or transaction.merchant_raw).lower()
        for pattern, category in sorted(self.rules.items(), key=lambda item: len(item[0]), reverse=True):
            normalised_pattern = re.escape(pattern)
            matches = (
                re.search(rf"\b{normalised_pattern}\b", merchant)
                if len(pattern) >= 4
                else merchant == pattern
            )
            if matches:
                return Prediction(category, 0.95, f"Merchant matches the '{pattern}' rule.", "RULE")
        return Prediction("Other", 0.20, "No merchant rule matched.", "RULE")
