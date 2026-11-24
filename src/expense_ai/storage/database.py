"""SQLAlchemy database setup."""

from sqlalchemy import Column, Float, Integer, MetaData, String, Table, DateTime, Text, create_engine
from sqlalchemy.orm import registry
from config.settings import DATABASE_PATH, DATABASE_URL


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


def create_database(database_url: str = DATABASE_URL) -> object:
    """Create engine, tables and parent directory."""
    database_path = DATABASE_PATH if database_url == DATABASE_URL else None
    if database_path:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url)
    metadata.create_all(engine)
    return engine
