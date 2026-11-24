# Evaluation Results

Measured on 2026-11-24 with the repository's seeded `SyntheticBankSource(seed=2026, months=6)` and `RuleCategoriser`.
Commands: `python scripts/evaluate.py` and `python scripts/simulate_user.py`.

## Categorisation

- Transactions evaluated: 725
- Accuracy: 89.6552%
- Errors: 75
- Questions at threshold 0.50: 79 (10.3448%)
- Questions at threshold 0.65: 79 (10.3448%)
- Questions at threshold 0.85: 79 (10.3448%)
- Error rate among predictions at thresholds 0.50, 0.65, and 0.85: 0.0000%

## Scripted feedback simulation

The script applied the simulated learner's merchant answers for four weekly batches and measured resulting prediction accuracy against `true_category`.

| Week | Questions | Answers in batch | Accuracy |
|---:|---:|---:|---:|
| 1 | 79 | 15 | 89.1034% |
| 2 | 79 | 602 | 100.0000% |
| 3 | 79 | 689 | 100.0000% |
| 4 | 79 | 690 | 100.0000% |
