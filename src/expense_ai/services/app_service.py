"""Application facade used by the Streamlit UI."""

from datetime import datetime
import json
from pathlib import Path
from typing import Iterable
from sqlalchemy.engine import Engine
from expense_ai.models.transaction import Transaction
from expense_ai.storage.repository import TransactionRepository
from expense_ai.ai.pipeline import CategorisationPipeline
from sqlalchemy import select, delete, insert, func
from sqlalchemy.orm import Session
from expense_ai.storage.database import (
    activity_log_table, questions_table, budgets_table, insights_table,
    transactions_table, feedback_table, merchant_rules_table,
)


class AppService:
    """Coordinate transaction ingestion and application queries."""

    def __init__(
        self,
        engine: Engine,
        pipeline: CategorisationPipeline,
        model_path: str | Path | None = None,
        enable_ml_training: bool = True,
    ) -> None:
        """Initialise service dependencies."""
        self.repository = TransactionRepository(engine)
        self.pipeline = pipeline
        self.model_path = model_path
        self.enable_ml_training = enable_ml_training
        from expense_ai.ai.clarification import ClarificationEngine
        self.clarification = ClarificationEngine(engine)
        from expense_ai.ai.categorisers.rule import RuleCategoriser
        from expense_ai.ai.categorisers.context import ContextCategoriser
        from expense_ai.ai.categorisers.fuzzy import FuzzyMerchantCategoriser
        from expense_ai.ai.categorisers.recurrence import RecurrenceDetector
        for categoriser in self.pipeline.categorisers:
            if isinstance(categoriser, (
                RuleCategoriser, ContextCategoriser, FuzzyMerchantCategoriser,
                RecurrenceDetector,
            )):
                categoriser.engine = engine
        self.clarification.release_questions()

    def configure_clarification(self, auto_threshold: float, ask_threshold: float,
                                max_questions_per_day: int) -> None:
        """Apply live thresholds to subsequent ingestion."""
        if auto_threshold <= ask_threshold:
            raise ValueError("Auto-accept threshold must exceed question threshold.")
        self.clarification.auto_threshold = auto_threshold
        self.clarification.ask_threshold = ask_threshold
        self.clarification.max_questions_per_day = max_questions_per_day

    def ingest(
        self, transaction: Transaction, release_questions: bool = True
    ) -> Transaction:
        """Categorise, clarify and persist one transaction."""
        prediction, options = self.pipeline.categorise_with_options(transaction)
        transaction.category = prediction.category
        transaction.confidence_score = prediction.confidence_score
        transaction.explanation = prediction.explanation
        transaction.method = prediction.method
        transaction.true_category = None
        saved = self.repository.add(transaction)
        clarification = self.clarification
        clarification.decide(saved, prediction, options, release=False)
        clarification.location_question(saved)
        clarification.extra_info_question(saved)
        clarification.recurring_question(saved)
        saved = self.repository.update(saved)
        if release_questions:
            clarification.release_questions()
        self.log_activity(
            saved.id,
            "AI_DECISION",
            f"Categorised {saved.merchant_clean} as {saved.category}.",
            method=saved.method,
            confidence=saved.confidence_score,
            explanation=saved.explanation,
        )
        return saved

    def ingest_all(self, transactions: Iterable[Transaction]) -> list[Transaction]:
        """Ingest a collection of transactions."""
        batch_cleanup = []
        for categoriser in self.pipeline.categorisers:
            begin_batch = getattr(categoriser, "begin_batch", None)
            if callable(begin_batch):
                begin_batch()
                end_batch = getattr(categoriser, "end_batch", None)
                if callable(end_batch):
                    batch_cleanup.append(end_batch)
        try:
            ingested = [
                self.ingest(transaction, release_questions=False)
                for transaction in transactions
            ]
        finally:
            for cleanup in batch_cleanup:
                cleanup()
        if self.enable_ml_training:
            self.train_ml_if_ready()
        self.clarification.release_questions()
        return ingested

    def get_transactions(self, limit: int | None = None) -> list[Transaction]:
        """List stored transactions."""
        return self.repository.list(limit)

    def get_pending_questions(self) -> list[object]:
        """Return simulated inbox questions."""
        with Session(self.repository.engine) as session:
            return [dict(row) for row in session.execute(
                select(questions_table).where(questions_table.c.status == "PENDING")
            ).mappings().all()]

    def get_queued_question_count(self) -> int:
        """Return the number of questions waiting to be surfaced."""
        from sqlalchemy import func

        with Session(self.repository.engine) as session:
            return int(session.execute(
                select(func.count()).select_from(questions_table).where(
                    questions_table.c.status == "QUEUED"
                )
            ).scalar_one())

    def release_next_question_batch(self) -> int:
        """Release one demo batch without applying questions already surfaced today."""
        return self.clarification.release_questions(ignore_daily_cap=True)

    def save_budget(self, category: str, monthly_limit: float, month: str) -> None:
        """Create or replace a category budget for a calendar month."""
        if monthly_limit < 0:
            raise ValueError("Budget limit cannot be negative")
        with Session(self.repository.engine) as session:
            existing = session.execute(select(budgets_table).where(
                budgets_table.c.category == category,
                budgets_table.c.month == month,
            ).limit(1)).first()
            if existing:
                session.execute(budgets_table.update().where(
                    budgets_table.c.category == category,
                    budgets_table.c.month == month,
                ).values(monthly_limit=monthly_limit))
            else:
                session.execute(insert(budgets_table).values(
                    category=category,
                    monthly_limit=monthly_limit,
                    month=month,
                ))
            session.commit()

    def get_budget_records(self) -> list[dict[str, object]]:
        """Return persisted budgets with IDs for editing and deletion."""
        with Session(self.repository.engine) as session:
            rows = session.execute(
                select(budgets_table).order_by(
                    budgets_table.c.month, budgets_table.c.category
                )
            ).mappings().all()
        return [dict(row) for row in rows]

    def update_budget(self, budget_id: int, monthly_limit: float) -> None:
        """Update a persisted budget's monthly limit."""
        if monthly_limit < 0:
            raise ValueError("Budget limit cannot be negative")
        with Session(self.repository.engine) as session:
            result = session.execute(budgets_table.update().where(
                budgets_table.c.id == budget_id
            ).values(monthly_limit=monthly_limit))
            if result.rowcount == 0:
                raise ValueError(f"Budget {budget_id} does not exist")
            session.commit()

    def delete_budget(self, budget_id: int) -> bool:
        """Delete a persisted budget by ID."""
        with Session(self.repository.engine) as session:
            result = session.execute(delete(budgets_table).where(
                budgets_table.c.id == budget_id
            ))
            session.commit()
        return result.rowcount > 0

    def reset_demo_data(self) -> None:
        """Clear every application table and remove the persisted ML model."""
        from config.settings import MODEL_PATH
        from expense_ai.storage.database import metadata

        with Session(self.repository.engine) as session:
            for table in reversed(metadata.sorted_tables):
                session.execute(delete(table))
            session.commit()
        model_path = Path(self.model_path or MODEL_PATH)
        if model_path.exists():
            model_path.unlink()

    def get_budgets(self, month: str) -> dict[str, float]:
        """Return recurring defaults overridden by budgets for the requested month."""
        with Session(self.repository.engine) as session:
            rows = session.execute(select(budgets_table).where(
                budgets_table.c.month.in_(("default", month))
            )).mappings().all()
        budgets = {
            row["category"]: float(row["monthly_limit"])
            for row in rows if row["month"] == "default"
        }
        budgets.update({
            row["category"]: float(row["monthly_limit"])
            for row in rows if row["month"] == month
        })
        return budgets

    def get_pending_insights(self) -> list[dict[str, object]]:
        """Return insight cards awaiting Accept or Dismiss."""
        with Session(self.repository.engine) as session:
            rows = session.execute(select(insights_table).where(
                insights_table.c.status == "PENDING"
            )).mappings().all()
        return [dict(row) for row in rows]

    def answer_question(self, question_id: int, answer: str) -> str | None:
        """Apply one answer to all pending questions of that type for the merchant."""
        with Session(self.repository.engine) as session:
            question = session.execute(
                select(questions_table).where(
                    questions_table.c.id == question_id,
                    questions_table.c.status == "PENDING",
                )
            ).mappings().first()
            if question is None:
                return None
            transaction_row = session.execute(
                select(transactions_table).where(
                    transactions_table.c.id == question["transaction_id"]
                )
            ).mappings().first()
            if transaction_row is None:
                return None
            is_category = question["question_type"] == "CATEGORY"
            is_location = question["question_type"] == "LOCATION"
            if is_location:
                merchant_questions = [
                    (question["id"], question["transaction_id"])
                ]
            elif not is_category:
                merchant_questions = session.execute(
                    select(questions_table.c.id, questions_table.c.transaction_id)
                    .join(
                        transactions_table,
                        questions_table.c.transaction_id == transactions_table.c.id,
                    )
                    .where(
                        questions_table.c.question_type == question["question_type"],
                        questions_table.c.status == "PENDING",
                        transactions_table.c.merchant_clean
                        == transaction_row["merchant_clean"],
                    )
                ).all()
        if is_category:
            category = answer.strip()
            if not category:
                raise ValueError("Category cannot be empty")
            return self._apply_category_answer(
                int(transaction_row["id"]), category
            )
        transaction = self.repository.get(question["transaction_id"])
        if transaction is None:
            return None
        transactions = [
            item for _, transaction_id in merchant_questions
            if (item := self.repository.get(transaction_id)) is not None
        ]
        question_ids = [question_id for question_id, _ in merchant_questions]
        for pending_question_id in question_ids:
            self.clarification.answer_question(pending_question_id, answer)
        count = len(transactions)
        merchant = transaction.merchant_clean if transaction else "Merchant"
        question_type = question["question_type"]
        if question_type == "LOCATION":
            message = f"{merchant} location set to {answer} for {count} transactions."
        elif question_type == "RECURRING":
            message = f"{merchant} recurring status set to {answer} for {count} transactions."
        else:
            message = f"Saved a note for {merchant} on {count} transactions."
        for item in transactions:
            self.log_activity(
                item.id,
                "ANSWER",
                message,
                method=item.method,
                confidence=item.confidence_score,
                explanation=item.explanation,
            )
        return message

    def correct_category(self, transaction_id: int, category: str) -> str:
        """Apply a manual correction through the same learning path as Inbox answers."""
        selected = category.strip()
        if not selected:
            raise ValueError("Category cannot be empty")
        return self._apply_category_answer(transaction_id, selected)

    def _apply_category_answer(
        self, transaction_id: int, category: str
    ) -> str:
        """Update merchant transactions and persist reversible learning state."""
        from expense_ai.ai.feedback import FeedbackLearner

        transaction = self.repository.get(transaction_id)
        if transaction is None:
            raise ValueError(f"Transaction {transaction_id} does not exist")
        now = datetime.now()
        with Session(self.repository.engine) as session:
            merchant_rows = session.execute(select(transactions_table).where(
                transactions_table.c.merchant_clean == transaction.merchant_clean
            )).mappings().all()
            affected = [
                dict(row) for row in merchant_rows
                if row["id"] == transaction_id
                or not (
                    row["method"] == "USER"
                    and row["status"] in ("CONFIRMED", "CORRECTED")
                    and row["category"] != category
                )
            ]
            category_questions = session.execute(
                select(questions_table)
                .join(
                    transactions_table,
                    questions_table.c.transaction_id == transactions_table.c.id,
                )
                .where(
                    transactions_table.c.merchant_clean == transaction.merchant_clean,
                    questions_table.c.question_type == "CATEGORY",
                    questions_table.c.status.in_(("PENDING", "QUEUED")),
                )
            ).mappings().all()
            rule = session.execute(select(merchant_rules_table).where(
                merchant_rules_table.c.pattern == transaction.merchant_clean
            )).mappings().first()
            previous_state: dict[str, object] = {
                "transactions": [
                    {
                        "id": row["id"],
                        "category": row["category"],
                        "status": row["status"],
                        "method": row["method"],
                        "confidence_score": row["confidence_score"],
                        "explanation": row["explanation"],
                    }
                    for row in affected
                ],
                "questions": [
                    {
                        "id": row["id"],
                        "status": row["status"],
                        "answer": row["answer"],
                        "answered_at": row["answered_at"],
                        "surfaced_at": row["surfaced_at"],
                    }
                    for row in category_questions
                ],
                "rule": dict(rule) if rule else None,
            }
            for row in affected:
                status = "CONFIRMED" if row["category"] == category else "CORRECTED"
                session.execute(transactions_table.update().where(
                    transactions_table.c.id == row["id"]
                ).values(
                    category=category,
                    status=status,
                    method="USER",
                    confidence_score=1.0,
                    explanation=f"Confirmed by you on {now.date().isoformat()}",
                ))
            for row in category_questions:
                session.execute(questions_table.update().where(
                    questions_table.c.id == row["id"]
                ).values(status="ANSWERED", answer=category, answered_at=now))
            session.commit()

        learner = FeedbackLearner(self.repository.engine)
        learner.record_answer(
            transaction, transaction.category, category, explicit=True
        )
        with Session(self.repository.engine) as session:
            previous_state["feedback_id"] = session.execute(
                select(func.max(feedback_table.c.id)).where(
                    feedback_table.c.transaction_id == transaction_id
                )
            ).scalar_one()
        message = (
            f"Confirmed {transaction.merchant_clean} as {category}; "
            f"updated {len(affected)} transactions."
        )
        self.log_activity(
            transaction_id,
            "CATEGORY_ANSWER",
            message,
            method="USER",
            confidence=1.0,
            explanation=f"Confirmed by you on {now.date().isoformat()}",
            previous_state=previous_state,
        )
        if learner.should_retrain():
            self.train_ml_if_ready()
        return message

    def log_activity(
        self,
        transaction_id: int | None,
        event_type: str,
        message: str,
        method: str | None = None,
        confidence: float | None = None,
        explanation: str | None = None,
        previous_state: dict[str, object] | None = None,
    ) -> None:
        """Persist a user-visible AI decision or data change."""
        if transaction_id is None:
            return
        with Session(self.repository.engine) as session:
            session.execute(activity_log_table.insert().values(
                transaction_id=transaction_id,
                event_type=event_type,
                message=message,
                method=method,
                confidence=confidence,
                explanation=explanation,
                previous_state=(
                    json.dumps(previous_state, default=lambda value: value.isoformat())
                    if previous_state is not None else None
                ),
                created_at=datetime.now(),
            ))
            session.commit()

    def get_last_category_action(self) -> dict[str, object] | None:
        """Return the most recent category action that can still be undone."""
        with Session(self.repository.engine) as session:
            row = session.execute(
                select(activity_log_table)
                .where(activity_log_table.c.event_type == "CATEGORY_ANSWER")
                .order_by(activity_log_table.c.created_at.desc(),
                          activity_log_table.c.id.desc())
                .limit(1)
            ).mappings().first()
        return dict(row) if row else None

    def undo_category_change(self, transaction_id: int | None = None) -> bool:
        """Restore the latest matching category action and its learning effects."""
        from expense_ai.ai.feedback import FeedbackLearner

        statement = select(activity_log_table).where(
            activity_log_table.c.event_type == "CATEGORY_ANSWER"
        )
        if transaction_id is not None:
            statement = statement.where(
                activity_log_table.c.transaction_id == transaction_id
            )
        statement = statement.order_by(
            activity_log_table.c.created_at.desc(),
            activity_log_table.c.id.desc(),
        ).limit(1)
        with Session(self.repository.engine) as session:
            action = session.execute(statement).mappings().first()
        if action is None or not action["previous_state"]:
            return False
        previous = json.loads(action["previous_state"])
        transaction = self.repository.get(int(action["transaction_id"]))
        if transaction is None:
            return False
        with Session(self.repository.engine) as session:
            for row in previous["transactions"]:
                session.execute(transactions_table.update().where(
                    transactions_table.c.id == row["id"]
                ).values(
                    category=row["category"],
                    status=row["status"],
                    method=row["method"],
                    confidence_score=row["confidence_score"],
                    explanation=row["explanation"],
                ))
            for row in previous["questions"]:
                session.execute(questions_table.update().where(
                    questions_table.c.id == row["id"]
                ).values(
                    status=row["status"],
                    answer=row["answer"],
                    answered_at=(
                        datetime.fromisoformat(row["answered_at"])
                        if row["answered_at"] else None
                    ),
                    surfaced_at=(
                        datetime.fromisoformat(row["surfaced_at"])
                        if row["surfaced_at"] else None
                    ),
                ))
            session.execute(activity_log_table.update().where(
                activity_log_table.c.id == action["id"]
            ).values(event_type="CATEGORY_ANSWER_UNDONE"))
            session.commit()
        FeedbackLearner(self.repository.engine).undo_correction(
            transaction,
            str(next(
                row["category"] for row in previous["transactions"]
                if row["id"] == transaction.id
            )),
            int(previous["feedback_id"]) if previous.get("feedback_id") else None,
            previous.get("rule"),
        )
        self.log_activity(
            transaction.id,
            "UNDO_CATEGORY_ANSWER",
            f"Undid category confirmation for {transaction.merchant_clean}.",
        )
        return True

    def get_activity_log(
        self, transaction_id: int | None = None, limit: int = 100
    ) -> list[dict[str, object]]:
        """Return recent activity, optionally for one transaction."""
        statement = select(activity_log_table).order_by(
            activity_log_table.c.created_at.desc()
        )
        if transaction_id is not None:
            statement = statement.where(
                activity_log_table.c.transaction_id == transaction_id
            )
        with Session(self.repository.engine) as session:
            rows = session.execute(statement.limit(limit)).mappings().all()
        return [dict(row) for row in rows]

    def train_ml_if_ready(self) -> bool:
        """Train the service ML categoriser once enough labelled rows exist."""
        from expense_ai.ai.categorisers.ml import MLCategoriser
        if not self.enable_ml_training:
            return False
        ml = next((item for item in self.pipeline.categorisers
                   if item.__class__.__name__ == "MLCategoriser"), None)
        if ml is None:
            ml = MLCategoriser(self.model_path) if self.model_path else MLCategoriser()
        labelled: list[Transaction] = []
        with Session(self.repository.engine) as session:
            from expense_ai.storage.database import feedback_table
            feedback = session.execute(select(feedback_table)).mappings().all()
        for row in feedback:
            transaction = self.repository.get(row["transaction_id"])
            if transaction:
                transaction.category = row["chosen_category"]
                labelled.append(transaction)
        for item in self.get_transactions():
            if item.method == "RULE" and item.confidence_score >= 0.85:
                labelled.append(item)
        labelled = [item for item in labelled if item.category != "Other"]
        deduplicated: dict[tuple[str, str], Transaction] = {}
        for item in labelled:
            merchant = (item.merchant_clean or item.merchant_raw).casefold().strip()
            deduplicated.setdefault((merchant, item.category), item)
        labelled = list(deduplicated.values())
        category_counts: dict[str, int] = {}
        for item in labelled:
            category_counts[item.category] = category_counts.get(item.category, 0) + 1
        labelled = [
            item for item in labelled if category_counts[item.category] >= 2
        ]
        if len(labelled) < 10 or len({item.category for item in labelled}) < 2:
            return False
        ml.train(
            [item.merchant_clean or item.merchant_raw for item in labelled],
            [item.category for item in labelled],
            [item.amount for item in labelled],
            [item.timestamp.hour for item in labelled],
        )
        if not ml.is_trained():
            return False
        if ml not in self.pipeline.categorisers:
            self.pipeline.categorisers.append(ml)
        return True
