# Human Evaluation Results

Run: `20260616-141015`

## Primary Captain Similarity Score

Primary score for this project: `0.45 * persona_consistency + 0.35 * style_similarity + 0.20 * relevance`.
This keeps the main judgment focused on whether the reply feels like Kappitan while still requiring the answer to fit the prompt.

| Model | Score | N |
| --- | ---: | ---: |
| `finetuned` | 3.95 | 528 |
| `baseline` | 2.28 | 528 |

## Mean Scores (1–5 scale)

| Metric | `finetuned` (mean ± SD; N) | `baseline` (mean ± SD; N) |
| --- | ---: | ---: |
| Persona Consistency | 3.90 ± 1.22; N=528 | 1.87 ± 1.30; N=528 |
| Style Similarity | 3.99 ± 1.25; N=528 | 2.11 ± 1.39; N=528 |
| Relevance | 3.99 ± 1.35; N=528 | 3.49 ± 1.50; N=528 |
| Context Consistency (multi-turn only) | 4.73 ± 0.69; N=120 | 4.62 ± 0.79; N=120 |

## Win Rate Analysis

| Metric | `finetuned` wins | `baseline` wins | Ties | `finetuned` rate |
| --- | ---: | ---: | ---: | ---: |
| Persona Consistency | 60 | 5 | 1 | 90.91% |
| Style Similarity | 61 | 3 | 2 | 92.42% |
| Relevance | 44 | 18 | 4 | 66.67% |

## Wilcoxon Signed-Rank Test (paired models)

> Testing paired `finetuned` and `baseline` scores
> using per-prompt means aggregated across evaluators and exact sign-permutation p-values.
> Positive rank-biserial r favors `finetuned`.

| Metric | N pairs | W stat | Rank-biserial r | p-value | Significant | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Persona Consistency | 65 | 25.5 | 0.9762 | <0.0001 | ✅ Yes | Significant difference (p<0.0001) |
| Style Similarity | 64 | 14.5 | 0.9861 | <0.0001 | ✅ Yes | Significant difference (p<0.0001) |
| Relevance | 62 | 421.0 | 0.5689 | <0.0001 | ✅ Yes | Significant difference (p<0.0001) |
| Context Consistency (multi-turn only) | 12 | 19.5 | 0.5000 | 0.1328 | ❌ No | No significant difference (p=0.1328 >= 0.05) |

## Inter-Rater Agreement

> Weighted Kappa (Quadratic) is appropriate for ordinal 1-5 scale.
> Agreement is calculated separately per model; Alpha uses interval distance.

| Metric | Weighted κ by model | Mean κ | Interpretation | Krippendorff's α by model (interval) |
| --- | --- | ---: | --- | --- |
| Persona Consistency | finetuned=0.2248; baseline=0.3945 | 0.3096 | Fair | finetuned=0.1415; baseline=0.3133 |
| Style Similarity | finetuned=0.1602; baseline=0.4037 | 0.2819 | Fair | finetuned=0.0249; baseline=0.3943 |
| Relevance | finetuned=0.172; baseline=0.3819 | 0.277 | Fair | finetuned=0.0575; baseline=0.3499 |
| Context Consistency (multi-turn only) | finetuned=0.2554; baseline=0.2777 | 0.2665 | Fair | finetuned=0.0238; baseline=0.0589 |

> **Kappa interpretation guide:** < 0.20 = Slight | 0.20-0.40 = Fair | 0.40-0.60 = Moderate | 0.60-0.80 = Substantial | > 0.80 = Almost perfect

---
*Analyzed 8 evaluator(s). Statistical tests are two-sided Wilcoxon Signed-Rank (non-parametric, appropriate for ordinal data).*
*Evaluator count: n=8. Interpret statistical power in light of the final sample size.*
