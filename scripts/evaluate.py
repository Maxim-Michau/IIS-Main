"""Report measured question and accuracy rates for a threshold matrix."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.simulate_user import run_simulation


THRESHOLDS = (
    (0.95, 0.70),
    (0.85, 0.50),
    (0.70, 0.30),
)


def evaluate() -> dict[str, dict[str, object]]:
    """Run reproducible, type-aware simulations using the real daily cap."""
    result: dict[str, dict[str, object]] = {}
    for auto_threshold, ask_threshold in THRESHOLDS:
        measured = run_simulation(
            auto_threshold,
            ask_threshold,
            question_cap=5,
            months=4,
        )
        result[f"{auto_threshold:.2f}/{ask_threshold:.2f}"] = measured
    return result


def main() -> None:
    """Print the measurements used by the evaluation report."""
    print(json.dumps(evaluate(), indent=2))


if __name__ == "__main__":
    main()
