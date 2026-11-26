"""SQLAlchemy database setup."""

import logging

from sqlalchemy import (Boolean, Column, Float, Integer, MetaData, String, Table,
                        DateTime, Text, create_engine, inspect)
from config.settings import DATABASE_PATH, DATABASE_URL


logger = logging.getLogger(__name__)
metadata = MetaData()
transactions_table = Table(
    "transactions", metadata,
    Column("id", Integer, primary_key=True),
    Column("timestamp", DateTime, nullable=False),
    Column("amount", Float, nullable=False),
    Column("merchant_raw", String, nullable=False),
    Column("merchant_clean", String, nullable=False),
    Column("location", String),
    Column("category", String, nullable=False),
    Column("confidence_score", Float, nullable=False),
    Column("status", String, nullable=False),
    Column("explanation", Text),
    Column("source", String, nullable=False),
    Column("true_category", String),
    Column("method", String, nullable=False),
    Column("is_recurring", Boolean, nullable=False, default=False),
    Column("note", Text),
    Column("mcc", String),
)
questions_table = Table(
    "questions", metadata,
    Column("id", Integer, primary_key=True),
    Column("transaction_id", Integer, nullable=False),
    Column("question_type", String, nullable=False),
    Column("prompt_text", Text, nullable=False),
    Column("options", Text),
    Column("status", String, nullable=False),
    Column("answer", String),
    Column("created_at", DateTime),
    Column("answered_at", DateTime),
    Column("surfaced_at", DateTime),
)
feedback_table = Table(
    "feedback", metadata,
    Column("id", Integer, primary_key=True),
    Column("transaction_id", Integer, nullable=False),
    Column("predicted_category", String, nullable=False),
    Column("chosen_category", String, nullable=False),
    Column("merchant_clean", String, nullable=False),
    Column("created_at", DateTime),
)
budgets_table = Table(
    "budgets", metadata,
    Column("id", Integer, primary_key=True),
    Column("category", String, nullable=False),
    Column("monthly_limit", Float, nullable=False),
    Column("month", String, nullable=False),
)
merchant_rules_table = Table(
    "merchant_rules", metadata,
    Column("id", Integer, primary_key=True),
    Column("pattern", String, nullable=False),
    Column("category", String, nullable=False),
    Column("origin", String, nullable=False),
    Column("times_confirmed", Integer, nullable=False),
)
insights_table = Table(
    "insights", metadata,
    Column("id", Integer, primary_key=True),
    Column("title", String, nullable=False),
    Column("explanation", Text, nullable=False),
    Column("estimated_monthly_saving", Float, nullable=False),
    Column("status", String, nullable=False),
)
activity_log_table = Table(
    "activity_log", metadata,
    Column("id", Integer, primary_key=True),
    Column("transaction_id", Integer, nullable=False),
    Column("event_type", String, nullable=False),
    Column("message", Text, nullable=False),
    Column("method", String),
    Column("confidence", Float),
    Column("explanation", Text),
    Column("previous_state", Text),
    Column("created_at", DateTime, nullable=False),
)


def create_database(database_url: str = DATABASE_URL) -> object:
    """Create engine, tables and parent directory."""
    database_path = DATABASE_PATH if database_url == DATABASE_URL else None
    if database_path:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url)
    metadata.create_all(engine)
    budget_columns = {
        column["name"] for column in inspect(engine).get_columns("budgets")
    }
    if "month" not in budget_columns:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE budgets ADD COLUMN month VARCHAR NOT NULL DEFAULT '1970-01'"
            )
        logger.info("Added missing budgets.month column.")
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            columns = {
                row[1] for row in connection.exec_driver_sql(
                    "PRAGMA table_info(transactions)"
                ).fetchall()
            }
            if "is_recurring" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE transactions ADD COLUMN is_recurring BOOLEAN NOT NULL DEFAULT 0"
                )
            if "note" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE transactions ADD COLUMN note TEXT"
                )
            if "mcc" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE transactions ADD COLUMN mcc TEXT"
                )
            question_columns = {
                row[1] for row in connection.exec_driver_sql(
                    "PRAGMA table_info(questions)"
                ).fetchall()
            }
            if "surfaced_at" not in question_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE questions ADD COLUMN surfaced_at DATETIME"
                )
            activity_columns = {
                row[1] for row in connection.exec_driver_sql(
                    "PRAGMA table_info(activity_log)"
                ).fetchall()
            }
            if "previous_state" not in activity_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE activity_log ADD COLUMN previous_state TEXT"
                )
    return engine
