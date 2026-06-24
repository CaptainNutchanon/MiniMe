# MiniMe Auto Evaluation Metrics

Run: `20260616-141015`

## Training Summary (Experimental Setup)

| Key | Value |
| --- | --- |
| Model | `Qwen/Qwen3.5-9B` |
| Best checkpoint | `checkpoint-900` |
| Best eval_loss | `3.3519` |
| Final train_loss | `2.9421` |
| Perplexity (exp(eval_loss)) | `28.56` *(reference only, not persona metric)* |
| Train examples | 3705 |
| Val examples | 478 |
| Epochs | 2 |
| Max completion chars | 60 |

### Overfitting Analysis

Maximum matched gap at step 800: train_loss=2.1495, val_loss=3.3661, **gap=1.2167**
*maximum gap > 1.0 suggests overfitting*
The matched gap first exceeds 1.0 at step 700.

### Loss Curve

| Step | Epoch | Train Loss | Val Loss | LR |
| ---: | ---: | ---: | ---: | ---: |
| 50 | 0.108 | 4.4036 |  | 2.00e-04 |
| 100 | 0.216 | 3.7274 |  | 1.98e-04 |
| 100 | 0.216 |  | 3.6690 |  |
| 150 | 0.324 | 3.6141 |  | 1.93e-04 |
| 200 | 0.432 | 3.4541 |  | 1.86e-04 |
| 200 | 0.432 |  | 3.5460 |  |
| 250 | 0.540 | 3.5498 |  | 1.75e-04 |
| 300 | 0.648 | 3.4539 |  | 1.62e-04 |
| 300 | 0.648 |  | 3.4455 |  |
| 350 | 0.756 | 3.1993 |  | 1.47e-04 |
| 400 | 0.864 | 3.2661 |  | 1.31e-04 |
| 400 | 0.864 |  | 3.4243 |  |
| 450 | 0.972 | 3.1454 |  | 1.14e-04 |
| 500 | 1.078 | 2.6421 |  | 9.59e-05 |
| 500 | 1.078 |  | 3.4122 |  |
| 550 | 1.186 | 2.4030 |  | 7.82e-05 |
| 600 | 1.294 | 2.4692 |  | 6.13e-05 |
| 600 | 1.294 |  | 3.3677 |  |
| 650 | 1.402 | 2.4769 |  | 4.55e-05 |
| 700 | 1.510 | 2.3296 |  | 3.15e-05 |
| 700 | 1.510 |  | 3.3643 |  |
| 750 | 1.618 | 2.2673 |  | 1.97e-05 |
| 800 | 1.726 | 2.1495 |  | 1.04e-05 |
| 800 | 1.726 |  | 3.3661 |  |
| 850 | 1.833 | 2.4626 |  | 3.94e-06 |
| 900 | 1.941 | 2.3215 |  | 5.34e-07 |
| 900 | 1.941 |  | 3.3519 |  |
| 928 | 2.000 |  | 3.3529 |  |
| 928 | 2.000 | 2.9421 |  |  |

## Real Kappitan Reply-Length Reference

The reference uses raw validation assistant targets after the same training filters. Curated examples are excluded. This is a corpus-level style reference, not a paired reference answer for each test prompt.

| Measure | Value |
| --- | ---: |
| Reference replies | 437 |
| Mean length | 15.85 chars |
| Median length | 12 chars |
| Range | 1-59 chars |

## Automatic Metrics

### Model: `baseline`

| Metric | Value |
| --- | --- |
| Total prompts | 66 |
| OK responses | 58 |
| Rejected (guard) | 8 |
| Guard rejection rate | 0.1212 |
| Avg reply length (chars) | 44.4000 |
| Reply-length ratio to real reference | 2.8018 |
| Median reply length (chars) | 49 |
| Long reply rate (>70 chars) | 0.0000 |
| Output artifact rate | 0.0000 |
| Emoji spam rate | 0.0000 |
| CJK/weird token rate | 0.0000 |
| Bad token rate | 0.0000 |
| Identity accuracy | 1.0000 |
| Identity retry rate | 0.0303 |
| Generic reply rate (open-ended) | 0.7143 |
| Avg retry count | 0.1360 |
| Distinct-1 (char-level) | 0.0378 |
| Distinct-2 (char-level) | 0.2482 |
| Avg latency (ms) | 1989.7000 |

### Model: `finetuned`

| Metric | Value |
| --- | --- |
| Total prompts | 66 |
| OK responses | 65 |
| Rejected (guard) | 1 |
| Guard rejection rate | 0.0152 |
| Avg reply length (chars) | 16.0000 |
| Reply-length ratio to real reference | 1.0097 |
| Median reply length (chars) | 12 |
| Long reply rate (>70 chars) | 0.0000 |
| Output artifact rate | 0.0152 |
| Emoji spam rate | 0.0000 |
| CJK/weird token rate | 0.0000 |
| Bad token rate | 0.0000 |
| Identity accuracy | 1.0000 |
| Identity retry rate | 0.0303 |
| Generic reply rate (open-ended) | 0.0000 |
| Avg retry count | 0.0910 |
| Distinct-1 (char-level) | 0.0554 |
| Distinct-2 (char-level) | 0.3386 |
| Avg latency (ms) | 1191.5000 |

## Comparison: `baseline` vs `finetuned`

| Metric | baseline | finetuned | Better |
| --- | ---: | ---: | --- |
| Guard rejection rate | 0.1212 | 0.0152 | finetuned |
| Avg reply length (chars) | 44.4000 | 16.0000 |  |
| Reply-length ratio to real reference | 2.8018 | 1.0097 | finetuned |
| Output artifact rate | 0.0000 | 0.0152 | baseline |
| Identity accuracy | 1.0000 | 1.0000 | tie |
| Generic reply rate | 0.7143 | 0.0000 | finetuned |
| Distinct-1 | 0.0378 | 0.0554 | finetuned |
| Distinct-2 | 0.2482 | 0.3386 | finetuned |
| Avg latency (ms) | 1989.7000 | 1191.5000 |  |

## Per-Category Breakdown: `baseline`

| Category | N | OK | Rejected | Avg Len | Identity Acc |
| --- | ---: | ---: | ---: | ---: | ---: |
| bot_identity | 3 | 3 | 0 | 29.0 | 1.00 |
| emotion_support | 7 | 5 | 2 | 59.8 | — |
| food_game_travel | 13 | 12 | 1 | 47.0 | — |
| greeting | 10 | 10 | 0 | 46.8 | — |
| identity | 5 | 5 | 0 | 8.0 | 1.00 |
| multi_turn | 15 | 15 | 0 | 47.7 | — |
| open_ended | 11 | 7 | 4 | 50.4 | — |
| privacy_status | 2 | 1 | 1 | 50.0 | — |

## Per-Category Breakdown: `finetuned`

| Category | N | OK | Rejected | Avg Len | Identity Acc |
| --- | ---: | ---: | ---: | ---: | ---: |
| bot_identity | 3 | 3 | 0 | 23.7 | 1.00 |
| emotion_support | 7 | 7 | 0 | 23.1 | — |
| food_game_travel | 13 | 12 | 1 | 13.7 | — |
| greeting | 10 | 10 | 0 | 8.9 | — |
| identity | 5 | 5 | 0 | 8.0 | 1.00 |
| multi_turn | 15 | 15 | 0 | 19.3 | — |
| open_ended | 11 | 11 | 0 | 17.4 | — |
| privacy_status | 2 | 2 | 0 | 16.0 | — |

---
*Auto metrics report generated by `evaluation/compute_metrics.py`.*
*Human evaluation scores (Persona Consistency, Style Similarity, Relevance) are separate — see `human_eval_summary.md`.*