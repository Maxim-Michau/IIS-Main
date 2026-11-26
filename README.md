# Expense AI

Expense AI is an offline-first personal finance assistant prototype for a UK university student. It uses transaction data to suggest spending categories, ask for clarification when needed, and present spending through dashboard, budget and advisor views.

## Project status

- **Implemented:** Streamlit interface with Dashboard, Inbox, Transactions, Advisor, Budgets and Settings views.
- **Implemented:** local SQLite storage, synthetic transaction generation, CSV source support, transaction categorisation, clarification questions, user corrections, activity history, budgets, charts and evaluation scripts.
- **Implemented:** rule, learned merchant, fuzzy, context and recurrence categorisation components. The pipeline compares predictions and can lower confidence when strong methods disagree.
- **Implemented:** optional machine-learning and LLM categoriser components are present in the code. Their availability in code does not mean they were enabled or demonstrated for the submitted version.
- **Simulated:** generated transactions and MCC fields represent example bank data. The project does not connect to a real bank. Scripted feedback or notifications, where shown, are simulations.
- **Planned:** Open Banking integration. `OpenBankingSource` is not a working bank connection.
- **Evaluation limitation:** the documented evaluation uses seeded synthetic transactions. Its 100% category accuracy result is limited to that generated sample; it does not establish accuracy on real financial data.

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

The full repository history is available from the [GitHub commits page](https://github.com/Maxim-Michau/IIS-Main/commits/main/). 

## Checks and author testing

I have ran `python -m pytest -v` and the current project has passed all tests.  
I have ran `python scripts/evaluate.py` and it has cprrectly generated the documented evaluation results.

## AI assistance

Claude and GitHub Copilot assisted with the project. It's generated code was reviewed and modified where needed.