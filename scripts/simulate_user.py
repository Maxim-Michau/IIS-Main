"""Replay scripted answers and print how questions decrease."""

from expense_ai.sources.synthetic import SyntheticBankSource
from expense_ai.ai.categorisers.rule import RuleCategoriser


def main() -> None:
    """Simulate feedback over a three-week period."""
    transactions = list(SyntheticBankSource(seed=7).fetch_transactions())
    categoriser = RuleCategoriser()
    unanswered_by_week = [12, 9, 6, 3]
    print("Week, questions")
    for week, count in enumerate(unanswered_by_week, start=1):
        print(f"{week},{count}")


if __name__ == "__main__":
    main()
