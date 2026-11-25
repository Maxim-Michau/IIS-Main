"""Seeded synthetic bank source."""

from datetime import date, datetime, timedelta
import random
from typing import Iterable
from expense_ai.models.transaction import Transaction
from expense_ai.sources.bank_source import BankSource


class SyntheticBankSource(BankSource):
    """Generate realistic Birmingham transactions with simulated bank MCC fields."""

    def __init__(
        self,
        seed: int = 2026,
        months: int = 6,
        end_date: date | datetime | None = None,
    ) -> None:
        """Initialise seeded data parameters and an optional fixed window end."""
        self.seed = seed
        self.months = months
        self.end_date = end_date

    def fetch_transactions(self) -> Iterable[Transaction]:
        """Generate transactions from the first month through the configured end date."""
        rng = random.Random(self.seed)
        end = self.end_date or date.today()
        end_day = end.date() if isinstance(end, datetime) else end
        start_month_index = end_day.year * 12 + end_day.month - 1 - (self.months - 1)
        start = date(
            start_month_index // 12,
            start_month_index % 12 + 1,
            1,
        )
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
            ("PAYPAL *UNKNOWN MERCHANT", "paypal unknown", "Shopping", 42.0),
            ("AMZN MARKETPLACE", "Amazon", "Shopping", 29.0),
            ("CO-OP 1845", "Co-op", "Groceries", 16.0),
            ("SQ *TINY CAFE", "Unknown Cafe", "Eating Out", 7.5),
            ("CARD PAYMENT CAFE 77", "Unknown Cafe", "Eating Out", 8.5),
        ]
        rows: list[Transaction] = []
        # MCC values below are simulated bank fields, not observed bank data.
        mcc_by_category = {
            "Groceries": "5411", "Eating Out": "5812", "Takeaways": "5814",
            "Transport": "4111", "Rent & Bills": "4900", "Subscriptions": "5816",
            "Shopping": "5941", "Entertainment": "5812", "Education": "5942",
            "Health & Fitness": "7997",
        }
        for day in range((end_day - start).days + 1):
            current = datetime.combine(start + timedelta(days=day), datetime.min.time())
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
                    location=location, category="Other", true_category=category,
                    confidence_score=0.0, status="TENTATIVE", source="SYNTHETIC",
                    mcc=mcc_by_category.get(category),
                ))
        for month in range(self.months):
            rent_month_index = start.year * 12 + start.month - 1 + month
            rent_date = date(
                rent_month_index // 12,
                rent_month_index % 12 + 1,
                1,
            )
            if rent_date > end_day:
                continue
            rent_month = datetime.combine(rent_date, datetime.min.time())
            rows.append(Transaction(
                id=None, timestamp=rent_month, amount=650.0,
                merchant_raw="STUDENT RENT", merchant_clean="Rent",
                location="Birmingham", category="Other", confidence_score=0.0,
                status="TENTATIVE", explanation="", source="SYNTHETIC",
                true_category="Rent & Bills", method="RULE",
                mcc=mcc_by_category["Rent & Bills"],
            ))
        return rows
