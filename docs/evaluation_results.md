# Evaluation Results

Measured by running `python scripts/evaluate.py` on 2026-11-25. Each run used
`SyntheticBankSource(seed=7, months=4, end_date=today)`, the RULE/FUZZY/CONTEXT
cascade, and the real five-question-per-simulated-day cap. The window covered
2026-08-01 through 2026-11-25 (17 seven-day reporting periods). Category
questions were answered with their hidden category; location questions used the
stored location (or Birmingham when missing); recurring questions were answered
No; extra-info questions were skipped.

| Auto / ask thresholds | Daily cap | Category questions | Category questions/week | All questions | All questions/week | Accuracy before | Accuracy after | Error rate after |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.95 / 0.70 | 5 | 19 | 1.12 | 192 | 11.29 | 100.00% | 100.00% | 0.00% |
| 0.85 / 0.50 | 5 | 19 | 1.12 | 191 | 11.24 | 100.00% | 100.00% | 0.00% |
| 0.70 / 0.30 | 5 | 12 | 0.71 | 185 | 10.88 | 100.00% | 100.00% | 0.00% |

Weekly category/all question counts are shown separately below. Each pair is
`category questions / all questions`.

| Week starting | 0.95 / 0.70 | 0.85 / 0.50 | 0.70 / 0.30 |
|---|---:|---:|---:|
| 2026-08-01 | 11 / 24 | 11 / 24 | 6 / 19 |
| 2026-08-08 | 2 / 15 | 2 / 15 | 3 / 16 |
| 2026-08-15 | 2 / 12 | 2 / 11 | 1 / 10 |
| 2026-08-22 | 3 / 11 | 3 / 11 | 1 / 9 |
| 2026-08-29 | 1 / 15 | 1 / 15 | 0 / 15 |
| 2026-09-05 | 0 / 10 | 0 / 10 | 0 / 10 |
| 2026-09-12 | 0 / 11 | 0 / 11 | 0 / 11 |
| 2026-09-19 | 0 / 8 | 0 / 8 | 0 / 8 |
| 2026-09-26 | 0 / 9 | 0 / 9 | 1 / 10 |
| 2026-10-03 | 0 / 11 | 0 / 11 | 0 / 11 |
| 2026-10-10 | 0 / 8 | 0 / 8 | 0 / 8 |
| 2026-10-17 | 0 / 10 | 0 / 10 | 0 / 10 |
| 2026-10-24 | 0 / 10 | 0 / 10 | 0 / 10 |
| 2026-10-31 | 0 / 9 | 0 / 9 | 0 / 9 |
| 2026-11-07 | 0 / 12 | 0 / 12 | 0 / 12 |
| 2026-11-14 | 0 / 13 | 0 / 13 | 0 / 13 |
| 2026-11-21 | 0 / 4 | 0 / 4 | 0 / 4 |

The 0.70 / 0.30 thresholds reduced category questions by 7 and all questions by
7 versus 0.95 / 0.70. The 0.85 / 0.50 setting reduced all questions by 1, with
no reduction in category questions. Baseline accuracy was already 100% on this
seeded synthetic sample, so feedback did not improve measured accuracy; this is
not evidence of improved accuracy on real bank data.

The measurements are produced from the generated data and actual clarification
records, not estimated. MCC values in the synthetic source are simulated bank
fields, not real bank-provided data.
