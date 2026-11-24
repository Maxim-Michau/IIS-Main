# expense-ai

An intelligent offline-first personal-finance assistant for a typical UK university student.

**Prose: approximately 180 words.**

## Status
- **Implemented:** synthetic ingestion, SQLite storage, rule/ML categorisation, mixed-initiative inbox, learning, insights, budgets, and offline advisor chat.
- **Simulated:** push notifications and demonstration transaction generation.
- **Planned:** `OpenBankingSource` is deliberately unimplemented for security.

## Stack
- Python 3.11+, pandas, SQLAlchemy/SQLite
- scikit-learn, joblib, and TF-IDF/logistic regression
- Streamlit and Plotly
- Pydantic-compatible dataclasses, Faker, pytest
- Optional Anthropic SDK, python-dotenv

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src:.
python scripts/generate_data.py
python -m pytest -q
streamlit run src/expense_ai/ui/app.py
```

## Optional LLM
Copy `.env.example` to `.env`, set `ANTHROPIC_API_KEY`, and set `USE_LLM=true`. The app remains fully usable without a key and falls back safely on LLM errors.

## Development record
1. Skeleton, models, SQLite and repository tests
2. Synthetic bank sources and seeded generator
3. Rules, cascade pipeline and ingestion
4. Streamlit dashboard and transaction page
5. Calibrated ML categoriser and evaluation
6. Clarification engine and simulated inbox
7. Feedback learning and undo
8. Insight engine and budgets
9. Optional LLM and grounded advisor
10. Simulation, evaluation and final cleanup

## AI assistance
GitHub Copilot was used to scaffold the repository; outputs were reviewed and changed by the author.

Evaluation documents live in `docs/evaluation_results.md`.
