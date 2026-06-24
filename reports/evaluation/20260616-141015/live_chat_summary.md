# Live Chat Evaluation Results

Run: `20260616-141015`

## Coverage

| Measure | Value |
| --- | ---: |
| Evaluators | 8 |
| Chat sessions | 22 |
| User prompts | 277 |

## Scores by Evaluator (1-5, primary)

| Metric | Mean ± SD | N | Direction |
| --- | ---: | ---: | --- |
| captain_similarity | 3.33 ± 0.98 | 8 | Higher is better |
| context_following | 3.44 ± 1.01 | 8 | Higher is better |
| problem_level | 2.85 ± 0.75 | 8 | Lower is better |

Each evaluator contributes one mean score, so evaluators with more chat sessions do not receive extra weight.

## Scores by Session (descriptive)

| Metric | Mean ± SD | N | Direction |
| --- | ---: | ---: | --- |
| captain_similarity | 3.27 ± 1.12 | 22 | Higher is better |
| context_following | 3.41 ± 1.10 | 22 | Higher is better |
| problem_level | 2.91 ± 0.97 | 22 | Lower is better |

## Response Quality

| Classification | Count | Rate |
| --- | ---: | ---: |
| Acceptable | 185 | 66.79% |
| Unacceptable | 92 | 33.21% |

Mean acceptable rate across evaluators: 68.10% (SD 19.30%, N=8).

Individual evaluator scores are retained only in the private JSON/CSV artifacts and are not included in this public summary.

---
*Live-chat scores are subjective user-study results. Report the evaluator and prompt counts with all means and rates.*
