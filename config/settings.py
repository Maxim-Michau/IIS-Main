"""Central settings for expense-ai."""

from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DATABASE_PATH = DATA_DIR / "expense_ai.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
MODEL_PATH = DATA_DIR / "categoriser.joblib"

AUTO_ACCEPT_THRESHOLD = 0.85
ASK_THRESHOLD = 0.50
MAX_QUESTIONS_PER_DAY = 5
RULE_PROMOTION_CONFIRMATIONS = 2
ML_RETRAIN_FEEDBACK_COUNT = 10
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"
