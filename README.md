# Expense AI

Expense AI is an offline-first personal finance assistant prototype for a UK university student. It uses transaction data to suggest spending categories, ask for clarification when needed, and present spending through dashboard, budget and advisor views.

<<<<<<< HEAD
## Project status

- **Implemented:** Streamlit interface with Dashboard, Inbox, Transactions, Advisor, Budgets and Settings views.
- **Implemented:** local SQLite storage, synthetic transaction generation, CSV source support, transaction categorisation, clarification questions, user corrections, activity history, budgets, charts and evaluation scripts.
- **Implemented:** rule, learned merchant, fuzzy, context and recurrence categorisation components. The pipeline compares predictions and can lower confidence when strong methods disagree.
- **Implemented:** optional machine-learning and LLM categoriser components are present in the code. Their availability in code does not mean they were enabled or demonstrated for the submitted version.
- **Simulated:** generated transactions and MCC fields represent example bank data. The project does not connect to a real bank. Scripted feedback or notifications, where shown, are simulations.
- **Planned:** Open Banking integration. `OpenBankingSource` is not a working bank connection.
- **Evaluation limitation:** the documented evaluation uses seeded synthetic transactions. Its 100% category accuracy result is limited to that generated sample; it does not establish accuracy on real financial data.
=======
> **README prose word count: 489 words.** Counts prose paragraphs and list items; excludes headings, fenced code, tables, and link destinations.

## Status

- **Implemented:** SQLite storage, synthetic ingestion, RULE/LEARNED/FUZZY/CONTEXT categorisation, optional ML/LLM methods, queued clarification, activity history and undo, monthly budgets, advisor charts, and measured evaluation.
- **Validation:** The full `python -m pytest -v` suite was run on Linux after each implementation stage. Stage-by-stage results are recorded below. `python -m scripts.evaluate` generated `docs/evaluation_results.md`.
- **Not validated here:** Windows PowerShell and macOS. Optional remote LLM operation and a manual interactive Streamlit session were also not run.
- **Limitations:** Open Banking is not implemented. MCC values, push notifications, and scripted feedback are simulated; evaluation results describe only the generated synthetic sample.
>>>>>>> 547fc1eee96da2673cb6867dfcd5bf49fe26db10

## Technology stack

- **Python 3.11 or newer** for application and evaluation logic.
- **Streamlit** for the interactive web interface.
- **SQLite and SQLAlchemy** for local transaction, question, budget and activity storage.
- **scikit-learn** for the optional machine-learning categoriser.
- **Anthropic API** for the optional LLM categoriser. REQUIRES YOU TO PROVIDE YOUR OWN API KEY.
- **pytest** for automated checks.

## Run or inspect the project

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
python scripts/generate_data.py
python -m pytest -v
streamlit run src/expense_ai/ui/app.py
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
python scripts/generate_data.py
python -m pytest -v
streamlit run src/expense_ai/ui/app.py
```

<<<<<<< HEAD
The app also has a button to generate demo transactions if its database is empty. To reproduce the documented evaluation, run:

```bash
python scripts/evaluate.py
```

See [`docs/evaluation_results.md`](docs/evaluation_results.md) for the evaluation setup, results and limitations. Main configuration is in `config/settings.py`; default category rules are in `config/default_rules.json`.

### Optional LLM setup

LLM categorisation is optional and off by default. If you choose to try it, create a local `.env` file based on `.env.example`, set `USE_LLM=true`, and provide your own `ANTHROPIC_API_KEY`as mentioned previously.

## Development record

- 5fa36bf Initial commit
- 5223ed6 Initial plan
- 04b3887 Skeleton: config, models, SQLite database, repository and tests
- e5de02c Bank sources: BankSource base class, synthetic, CSV and a deliberately unimplemented Open Banking source
- 88bcee1 Rule categoriser, cascade pipeline and ingestion service
- 995f56b Bulk stage: ML and LLM categorisers, clarification, feedback, insights, advisor, Streamlit pages, evaluation scripts
- 82fbb09 Import fix: pyproject.toml, pytest.ini, missing **\_\_init\_\_**.py files
- 1f353d2 Pages became routed views and sidebar navigation; pipeline factory; empty-database "generate" button
- 1971e69 Question types, feedback learner, deeper insights
- e46b2df First measured evaluation and simulation
- 569bda2 Ingestion now runs the real AI flow, and the generator no longer supplies categories
- 12d1cc4 ML trained from feedback, not ground truth; pipeline_factory.py
- 7683f7a Advisor with category synonyms, month filters and chat
- afea3bf Budgets and insight actions saved to the database
- aa2815c Working settings (live thresholds, fresh simulation) and inbox controls
- e9c424c Threshold-matrix evaluation
- 13e4a5e ML retrains after a persisted model loads
- 0a5f1cc Type-aware answers: location, recurring and note no longer overwrite the category. Learned rules are now loaded by the rule categoriser
- be4d21f Fuzzy, context (with simulated MCC) and recurrence categorisers; method-disagreement logic
- 89fbebd Inbox grouped by merchant with full context, custom category and location input, activity log
- 04f95bd Advisor chart grouping fix
- a4f1b35 Recurring budgets (default month), shared month selector, overspend display
- e8c4bd5 Synthetic data window ends at the configured date (default today)
- 4d56733 Type-aware evaluation with a daily cap
=======
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
>>>>>>> 547fc1eee96da2673cb6867dfcd5bf49fe26db10

The full repository history is available from the [GitHub commits page](https://github.com/Maxim-Michau/IIS-Main/commits/main/). 

<<<<<<< HEAD
## Checks and author testing

I have ran `python -m pytest -v` and the current project has passed all tests.  
I have ran `python scripts/evaluate.py` and it has cprrectly generated the documented evaluation results.

## AI assistance

Claude and GitHub Copilot assisted with the project. It's generated code was reviewed and modified where needed.
=======
See `docs/evaluation_results.md` for measured synthetic evaluation results. The latest recorded evaluation reports 100.00% held-out accuracy with simulated feedback and 85.39% without it; these values apply only to that synthetic sample.

## AI assistance

GitHub Copilot (agent mode) generated most of the code from prompts written with Claude's help.

**Personal checks and changes (to be completed by me):** [PLACEHOLDER — describe what I personally checked and changed.]
>>>>>>> 547fc1eee96da2673cb6867dfcd5bf49fe26db10
