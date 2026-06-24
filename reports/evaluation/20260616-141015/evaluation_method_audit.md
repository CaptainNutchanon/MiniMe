# Evaluation Method Audit

Run: `20260616-141015`

## Verdict

- Human blind A/B: calculations are valid after correcting Wilcoxon to exact sign-permutation and reporting agreement separately per model.
- Live chat: aggregation is valid as a descriptive evaluation of the fine-tuned model.
- The agreed core framework is complete. Reply length uses a corpus-level real validation reference because the 66 clean prompts do not have paired human replies.

## Human Blind A/B Checks

| Check | Result |
| --- | --- |
| Prompt structure | 66 valid prompts, no duplicate IDs |
| Train/val verbatim contamination | 0 matches across 7,263 checked messages |
| Response coverage | Baseline and fine-tuned each cover all 66 prompts |
| Blind mapping | Covers all 66 prompts and correctly maps A/B per prompt |
| Evaluator coverage | 8 evaluators, 66 rows each |
| Score completeness | 3,408 submitted score cells, 0 missing |
| Score range | Every score is within 1-5 |
| Independent recalculation | Reproduced all means and Captain Similarity scores |
| Paired test | Per-prompt evaluator means, exact Wilcoxon sign-permutation |
| Effect size | Rank-biserial correlation reported |
| Inter-rater agreement | Quadratic Weighted Kappa and interval-distance Alpha, separated by model |

The same randomized A/B sheet was used by all evaluators. Overall A placement is near-balanced (baseline 35, fine-tuned 31), but assignment is not stratified by category. This does not invalidate the paired overall result, but it limits position-bias and category-level interpretation.

## Live Chat Checks

| Check | Result |
| --- | --- |
| Evaluators | 8 |
| Sessions | 22 |
| User prompts | 277 |
| Minimum prompts per evaluator | 30 |
| Binary classification | 185 acceptable + 92 unacceptable = 277 |
| Primary score weighting | Mean within evaluator, then mean across 8 evaluators |
| Pooled acceptable rate | 66.79% |
| Equal-evaluator acceptable rate | 68.10% ± 19.30% |

Live chat is descriptive only. It has no baseline condition, no shared conversations across raters, and no submitted turn-level transcripts. Therefore no baseline significance test or live-chat inter-rater agreement should be reported.

## Metric Coverage Against the Agreed Framework

| Metric or artifact | Status | Note |
| --- | --- | --- |
| Train/eval loss values | Complete | Table and matched overfitting gap available |
| Best checkpoint | Complete | checkpoint-900 |
| Dataset statistics | Complete | 3,705 train / 478 validation examples |
| Perplexity reference | Complete | 28.56 from best eval loss |
| Rendered loss-curve graph | Complete | Two-epoch PNG and editable XLSX generated from the training log |
| Persona Consistency | Complete | Human blind A/B |
| Style Similarity | Complete | Human blind A/B |
| Relevance | Complete | Human blind A/B |
| Context Consistency | Complete | Multi-turn subset |
| Weighted Kappa | Complete | Reported per model and as a mean |
| Wilcoxon + effect size | Complete | Exact p-value and rank-biserial r |
| Average reply length | Complete | Baseline and fine-tuned |
| Reply-length ratio to real reference | Complete with caveat | Uses 437 raw validation replies as a corpus-level reference; not paired per prompt |
| Distinct-1 / Distinct-2 | Complete | Character-level for Thai text |
| Output artifact rate | Complete | Uses runtime garbage checks |
| Guard rejection rate | Complete | Baseline and fine-tuned |
| Identity retry rate | Complete | Baseline and fine-tuned |
| Live Captain similarity | Complete | Fine-tuned only |
| Live context/problem scores | Complete | Fine-tuned only |
| Live acceptable rate | Complete | Fine-tuned only |

Coherence and naturalness are intentionally not separate metrics: coherence is represented by multi-turn Context Consistency, while naturalness overlaps with Style Similarity for this persona-focused task.

## Interpretation Boundary

The evidence supports the claim that fine-tuning improves Kappitan persona and style on the blind test set. It does not support a statistically significant context improvement, and the live-chat data does not compare against baseline. Low agreement on fine-tuned style, relevance, and context means conclusions should include evaluator disagreement as a limitation.
