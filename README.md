# expense-ai

An offline-first personal-finance assistant for a UK university student, built with Python, Streamlit, SQLite and scikit-learn.

## Status

- **Implemented:** SQLite storage, synthetic ingestion, RULE/LEARNED/FUZZY/CONTEXT categorisation, optional ML/LLM methods, grouped clarification, activity history, monthly budgets, advisor charts, and measured evaluation.
- **Validated in this session:** `python -m pytest -v` on Linux passed 37 tests; `python scripts/evaluate.py` produced the results in `docs/evaluation_results.md`. Streamlit view smoke tests ran as part of pytest. Windows and macOS were not run in this session.
- **Limited:** Open Banking is not implemented. Optional LLM operation and a manual interactive Streamlit session were not run.
- **Simulated:** MCC values are synthetic bank-field examples; push notifications and scripted feedback are simulated.
- **Planned:** `OpenBankingSource` is not implemented. No live bank connection is claimed.

## Run on Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python scripts/generate_data.py
python -m pytest -v
streamlit run src/expense_ai/ui/app.py
```

## Run on Mac/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
python scripts/generate_data.py
python -m pytest -v
streamlit run src/expense_ai/ui/app.py
```

The app also offers an in-browser button to generate synthetic data when the database is empty.

## Optional LLM key

Copy `.env.example` to `.env`, set `USE_LLM=true`, and set `ANTHROPIC_API_KEY` to your own key. Never commit `.env`. LLM use is optional and every answer should remain grounded in repository data.

## Development record

1. Added type-aware answers, learned merchant rules, and multiple categorisation signals.
2. Grouped Inbox questions by merchant and persisted an activity history.
3. Added data-backed budgets, monthly charts, and an evaluation with a real daily question cap.

## Measured evaluation

See `docs/evaluation_results.md` for measured synthetic evaluation results.

## AI assistance

GitHub Copilot assisted with implementation and tests. The generated code was reviewed and modified in this repository.
