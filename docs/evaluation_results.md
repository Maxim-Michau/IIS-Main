# Evaluation Results

Measured on 2026-11-24 by running `python scripts/evaluate.py` with the seeded
`SyntheticBankSource(seed=7, months=4)` and the real `AppService.ingestion`,
`ClarificationEngine`, and `RuleCategoriser` cascade. The daily question cap was
set to 100 for the threshold matrix so it did not erase threshold effects.

## Real question results

Before feedback, accuracy against hidden `true_category` labels was 78.8889%.
After four 90-transaction batches and 100 scripted answers per week, accuracy
after feedback ranged from 98.6111% to 98.8889%, depending on thresholds.
The measured error rate after feedback ranged from 1.1111% to 1.3889%.

| Thresholds (auto/ask) | Questions | Weekly questions | Before accuracy | After accuracy | Error rate |
|---|---:|---:|---:|---:|---:|
| 0.95 / 0.70 | 400 | 100 / 100 / 100 / 100 | 78.8889% | 98.6111% | 1.3889% |
| 0.85 / 0.50 | 400 | 100 / 100 / 100 / 100 | 78.8889% | 98.8889% | 1.1111% |
| 0.70 / 0.30 | 400 | 100 / 100 / 100 / 100 | 78.8889% | 98.8889% | 1.1111% |

## Learning and thresholds

Learning reduced prediction error in this run, from 21.1111% to 1.1111%-1.3889%.
However, all three threshold pairs asked 400 questions in total and produced
the same weekly counts. Therefore, these particular threshold values did not
change the question count for this seeded dataset; the result is reported rather
than presented as a threshold effect.
