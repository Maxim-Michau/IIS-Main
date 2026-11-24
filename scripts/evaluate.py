"""Evaluate real clarification questions and feedback accuracy."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.simulate_user import run_simulation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def evaluate() -> dict[str, dict[str, object]]:
    """Report before/after accuracy and question/error rates."""
    settings = (
        (0.95, 0.70),
        (0.85, 0.50),
        (0.70, 0.30),
    )
    result: dict[str, dict[str, object]] = {}
    for auto_threshold, ask_threshold in settings:
        measured = run_simulation(auto_threshold, ask_threshold, question_cap=100)
        weekly = measured["weekly"]
        questions = sum(int(row["questions"]) for row in weekly)
        stored = 0
        for row in weekly:
            stored += int(row["answers"])
        error_rate = 1.0 - float(measured["after_accuracy"])
        result[f"{auto_threshold:.2f}/{ask_threshold:.2f}"] = {
            "questions": questions,
            "question_rate": questions / max(1, stored + questions),
            "before_accuracy": measured["before_accuracy"],
            "after_accuracy": measured["after_accuracy"],
            "error_rate": error_rate,
            "weekly": weekly,
        }
    logger.info("Evaluation: %s", result)
    return result


if __name__ == "__main__":
    evaluate()
