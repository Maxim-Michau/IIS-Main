"""Seeded synthetic bank source."""

from datetime import datetime, timedelta
import random
from typing import Iterable
from expense_ai.models.transaction import Transaction
from expense_ai.sources.bank_source import BankSource


class SyntheticBankSource(BankSource):
    """Generate realistic Birmingham student transactions."""

    def __init__(self, seed: int = 2026, months: int = 6) -> None:
        """Initialise reproducible data parameters."""
        self.seed = seed
        self.months = months

    def fetch_transactions(self) -> Iterable[Transaction]:
        """Generate approximately six months of transactions."""
        rng = random.Random(self.seed)
        start = datetime(2026, 1, 1)
        merchants = [
            ("TESCO STORES 4521", "Tesco", "Groceries", 18.0),
            ("ALDI PAY", "Aldi", "Groceries", 24.0),
            ("SAINSBURYS S/MKT", "Sainsbury's", "Groceries", 22.0),
            ("GREGGS", "Greggs", "Eating Out", 4.5),
            ("COSTA COFFEE", "Costa", "Eating Out", 5.0),
            ("SQ *DOUGHBALLS BHAM", "Doughballs", "Eating Out", 16.0),
            ("UBER EATS", "Uber Eats", "Takeaways", 18.0),
            ("DELIVEROO", "Deliveroo", "Takeaways", 20.0),
            ("WEST MIDLANDS RAILWAY", "West Midlands Railway", "Transport", 8.0),
            ("TFL TRAVEL", "TfL", "Transport", 7.0),
            ("SPOTIFY", "Spotify", "Subscriptions", 11.99),
            ("NETFLIX.COM", "Netflix", "Subscriptions", 12.99),
            ("AMZNMKTPLACE", "Amazon", "Shopping", 35.0),
            ("PAYPAL *JDSPORTS", "JD Sports", "Shopping", 55.0),
            ("STUDENT UNION SHOP", "Student Union", "Entertainment", 12.0),
            ("GYM MEMBERSHIP", "Gym", "Health & Fitness", 30.0),
            ("PEARSON TEXTBOOK", "Textbook", "Education", 48.0),
            ("CAMPUS PRINTING", "Printing", "Education", 6.0),
        ]
        rows: list[Transaction] = []
        for day in range(self.months * 30):
            current = start + timedelta(days=day)
            count = 3 if day % 3 else 5
            if day > 120:
                count += 1
            for _ in range(count):
                merchant_raw, merchant_clean, category, typical = rng.choice(merchants)
                amount = round(max(1.0, rng.normalvariate(typical, typical * 0.25)), 2)
                location = rng.choice(["Birmingham", "Birmingham", "Birmingham", "Manchester", None])
                rows.append(Transaction(
                    id=None, timestamp=current.replace(hour=rng.choice([8, 10, 12, 14, 18, 21, 23]),
                                                         minute=rng.choice([0, 15, 30, 45]),
                                                         second=0),
                    amount=amount, merchant_raw=merchant_raw, merchant_clean=merchant_clean,
                    location=location, category=category, true_category=category,
                    confidence_score=0.0, status="TENTATIVE", source="SYNTHETIC",
                ))
        rent = datetime(2026, 1, 1)
        for month in range(self.months):
            rent_month = rent.replace(month=min(rent.month + month, 12),
                                      year=rent.year + ((rent.month + month - 1) // 12))
            rows.append(Transaction(None, rent_month, 650.0, "STUDENT RENT", "Rent",
                                    "Birmingham", "Rent & Bills", 1.0, "AUTO",
                                    "Fixed recurring payment", "SYNTHETIC", "Rent & Bills", "RULE"))
        return rows
