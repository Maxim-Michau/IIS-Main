# expense-ai

An offline-first personal-finance assistant for a UK university student, built with Python, Streamlit, SQLite and scikit-learn.

> **README prose word count: 489 words.** Counts prose paragraphs and list items; excludes headings, fenced code, tables, and link destinations.

## Status

- **Implemented:** SQLite storage, synthetic ingestion, RULE/LEARNED/FUZZY/CONTEXT categorisation, optional ML/LLM methods, queued clarification, activity history and undo, monthly budgets, advisor charts, and measured evaluation.
- **Validation:** The full `python -m pytest -v` suite was run on Linux after each implementation stage. Stage-by-stage results are recorded below. `python -m scripts.evaluate` generated `docs/evaluation_results.md`.
- **Not validated here:** Windows PowerShell and macOS. Optional remote LLM operation and a manual interactive Streamlit session were also not run.
- **Limitations:** Open Banking is not implemented. MCC values, push notifications, and scripted feedback are simulated; evaluation results describe only the generated synthetic sample.

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

The app also offers an in-browser button to generate synthetic data when the database is empty. The generator refuses to overwrite an existing dataset unless `--reset` is provided.

## Configuration

Set `EXPENSE_AI_DATABASE_URL` to override the default SQLite database URL; this is useful for isolated test and development databases. For optional transaction categorisation with an LLM, copy `.env.example` to `.env`, set `USE_LLM=true`, and set `ANTHROPIC_API_KEY` to your own key. Never commit `.env`. Advisor answers remain offline and use repository data.

## Development record

### Stage 1 — question queue and daily cap

- Commit: [1dee180](https://github.com/Maxim-Michau/IIS-Main/commit/1dee180). Added queued questions, priority release, surfaced-date tracking, and Inbox controls.
- Checked: `python -m pytest -v` — **39 passed in 2.61s**.

### Stage 2 — learning and undo

- Commit: [83ac748](https://github.com/Maxim-Michau/IIS-Main/commit/83ac748). Applied merchant-wide category feedback, learned rules, reversible actions, and ML robustness.
- Checked: `python -m pytest -v` — **42 passed in 2.65s**.

### Stage 3 — categorisation logic

- Commit: [e7cda59](https://github.com/Maxim-Michau/IIS-Main/commit/e7cda59). Added source-aware cascade behavior, supporting context and recurrence signals, conditional/cached LLM calls, and tolerant LLM parsing.
- Checked: `python -m pytest -v` — **47 passed in 2.75s**.

### Stage 4 — evaluation and realistic data

- Commit: [65c9ae0](https://github.com/Maxim-Michau/IIS-Main/commit/65c9ae0). Updated synthetic data and time-held-out evaluation to use the application pipeline and question queue.
- Checked: `python -m pytest -v` — **48 passed in 3.44s**; `python -m scripts.evaluate` generated the evaluation report.

### Stage 5 — insights, budgets, and advisor

- Commit: [6b0d624](https://github.com/Maxim-Michau/IIS-Main/commit/6b0d624). Added data-backed savings and subscription insights, persisted insight actions, budget editing, and advisor query improvements.
- Checked: `python -m pytest -v` — **55 passed in 3.52s**.

### Stage 6 — UI and robustness

- Commit: [30213ca](https://github.com/Maxim-Michau/IIS-Main/commit/30213ca). Hardened search, merchant-specific location questions, resets, data generation, and batch categoriser lookups.
- Checked: `python -m pytest -v` — **61 passed in 3.89s**.

### Stage 7 — test isolation

- Commit: [e6a7a33](https://github.com/Maxim-Michau/IIS-Main/commit/e6a7a33). Added `EXPENSE_AI_DATABASE_URL` support and seeded temporary-database AppTest flows, including Inbox answering.
- Checked: `python -m pytest -v` — **65 passed in 5.00s**.

### Stage 8 — README and documentation

- Commit: [ae72c94](https://github.com/Maxim-Michau/IIS-Main/commit/ae72c94) added the computed README prose count, this staged development record, and the AI-assistance disclosure.
- Checked: `python -m pytest -v` — **65 passed in 4.92s**.

## Measured evaluation

See `docs/evaluation_results.md` for measured synthetic evaluation results. The latest recorded evaluation reports 100.00% held-out accuracy with simulated feedback and 85.39% without it; these values apply only to that synthetic sample.

## AI assistance

GitHub Copilot (agent mode) generated most of the code from prompts written with Claude's help.

**Personal checks and changes (to be completed by me):** [PLACEHOLDER — describe what I personally checked and changed.]
