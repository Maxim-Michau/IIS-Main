"""Learning from user feedback."""

from datetime import datetime
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from expense_ai.models.transaction import Transaction
from expense_ai.storage.database import feedback_table, merchant_rules_table
from config.settings import RULE_PROMOTION_CONFIRMATIONS, ML_RETRAIN_FEEDBACK_COUNT


class FeedbackLearner:
    """Store answers, promote rules, and trigger model retraining."""

    def __init__(self, engine: Engine, promotion_count: int = RULE_PROMOTION_CONFIRMATIONS,
                 retrain_count: int = ML_RETRAIN_FEEDBACK_COUNT) -> None:
        """Configure feedback learning thresholds."""
        self.engine = engine
        self.promotion_count = promotion_count
        self.retrain_count = retrain_count

    def record_answer(self, transaction: Transaction, predicted_category: str,
                      chosen_category: str) -> bool:
        """Store feedback and promote a merchant rule when confirmed enough times."""
        with Session(self.engine) as session:
            session.execute(insert(feedback_table).values(
                transaction_id=transaction.id,
                predicted_category=predicted_category,
                chosen_category=chosen_category,
                merchant_clean=transaction.merchant_clean,
                created_at=datetime.now(),
            ))
            session.commit()
        transaction.category = chosen_category
        transaction.status = "CORRECTED" if predicted_category != chosen_category else "CONFIRMED"
        should_promote = self._confirmation_count(transaction.merchant_clean, chosen_category)
        if should_promote >= self.promotion_count:
            self._promote_rule(transaction.merchant_clean, chosen_category)
        return should_promote >= self.promotion_count

    def undo_correction(self, transaction: Transaction, previous_category: str) -> None:
        """Restore a transaction category after a correction."""
        with Session(self.engine) as session:
            session.execute(delete(feedback_table).where(
                feedback_table.c.transaction_id == transaction.id,
            ))
            rule = session.execute(select(merchant_rules_table).where(
                merchant_rules_table.c.pattern == transaction.merchant_clean
            )).mappings().first()
            if rule:
                if rule["times_confirmed"] <= 1:
                    session.execute(delete(merchant_rules_table).where(
                        merchant_rules_table.c.pattern == transaction.merchant_clean
                    ))
                else:
                    session.execute(merchant_rules_table.update().where(
                        merchant_rules_table.c.pattern == transaction.merchant_clean
                    ).values(times_confirmed=rule["times_confirmed"] - 1))
            session.commit()
        transaction.category = previous_category
        transaction.status = "TENTATIVE"

    def should_retrain(self) -> bool:
        """Report whether the new-feedback threshold has been reached."""
        with Session(self.engine) as session:
            rows = session.execute(select(feedback_table)).all()
        return len(rows) >= self.retrain_count

    def metrics(self) -> dict[str, int]:
        """Return durable, repository-level learning metrics."""
        with Session(self.engine) as session:
            rows = session.execute(select(feedback_table)).mappings().all()
        confirmed = sum(row["predicted_category"] == row["chosen_category"] for row in rows)
        corrected = len(rows) - confirmed
        return {
            "feedback_rows": len(rows),
            "confirmed": confirmed,
            "corrected": corrected,
        }

    def _confirmation_count(self, merchant: str, category: str) -> int:
        """Count matching confirmed feedback rows."""
        with Session(self.engine) as session:
            rows = session.execute(select(feedback_table).where(
                feedback_table.c.merchant_clean == merchant,
                feedback_table.c.chosen_category == category,
            )).all()
        return len(rows)

    def _promote_rule(self, merchant: str, category: str) -> None:
        """Add or increment a learned merchant rule."""
        with Session(self.engine) as session:
            existing = session.execute(select(merchant_rules_table).where(
                merchant_rules_table.c.pattern == merchant
            )).mappings().first()
            if existing:
                session.execute(merchant_rules_table.update().where(
                    merchant_rules_table.c.pattern == merchant
                ).values(times_confirmed=existing["times_confirmed"] + 1))
            else:
                session.execute(insert(merchant_rules_table).values(
                    pattern=merchant, category=category,
                    origin="LEARNED", times_confirmed=self.promotion_count,
                ))
            session.commit()
