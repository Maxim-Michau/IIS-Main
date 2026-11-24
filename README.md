# expense-ai

An offline-first personal-finance assistant for a UK university student, built with Python, Streamlit, SQLite and scikit-learn.

**README prose word count: 267 words**

## Status

- **Implemented:** package installation, SQLite storage, synthetic ingestion through the categorisation and clarification pipeline, rule categorisation, Streamlit routing, chat advisor, monthly budgets, insight cards, live settings, feedback storage, and evaluation scripts. The full pytest suite and scripts were run.
- **Limited:** calibrated ML training exists and activates from confirmed/corrected or high-confidence rule labels, but no separate retrained-model smoke run was completed.
- **Simulated:** push notifications and the scripted feedback workflow; app transaction simulation creates a fresh local batch.
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

1. Fixed editable package imports and pytest discovery.
2. Replaced standalone page scripts with routed Streamlit views.
3. Added calibration, clarification, feedback, insight and grounded-advisor behavior.
4. Replaced placeholder evaluation with measured synthetic-data scripts and results.
5. Cleaned README status and run instructions.

## Measured evaluation

See `docs/evaluation_results.md`. It contains only figures printed by the repository scripts.

## AI assistance

GitHub Copilot assisted with implementation and tests. The generated code was reviewed and modified in this repository.

## Author's personally checked notes

**[PLACEHOLDER: The author must fill this section after personally testing Windows, macOS/Linux, Streamlit, and the generated demo. No personal verification is claimed here.]**
