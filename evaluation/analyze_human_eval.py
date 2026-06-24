"""
evaluation/analyze_human_eval.py

Analyze human evaluation results.

- Reads scored CSVs from evaluators
- Computes Mean ± SD per metric per model
- Computes Weighted Kappa (Quadratic) between evaluator pairs
- Computes Krippendorff's Alpha across all evaluators
- Runs Wilcoxon Signed-Rank Test for baseline vs fine-tuned comparison (if A/B)
- Outputs JSON + Markdown summary

Usage (A/B with 3 evaluators):
  python evaluation/analyze_human_eval.py --run-dir 20260612-163000 \\
      --eval-csvs rater1.csv rater2.csv rater3.csv

Usage (single model, 3 evaluators):
  python evaluation/analyze_human_eval.py --run-dir 20260612-163000 \\
      --eval-csvs rater1.csv rater2.csv rater3.csv --single-model

Notes:
- Evaluators should have filled in score columns (1-5) in the blind CSV
- Each rater CSV must be a copy of human_eval_blind.csv with scores filled in
- Evaluators should NOT have changed the prompt_id or response columns
"""

import argparse
import csv
import json
import math
import sys
import warnings
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minime_core.runtime_env import configure_utf8

configure_utf8()

REPORTS_BASE = ROOT / "reports" / "evaluation"
SEED = 42

SINGLE_TURN_METRICS = ["persona_consistency", "style_similarity", "relevance"]
MULTI_TURN_METRICS = ["persona_consistency", "style_similarity", "relevance", "context_consistency"]
ALL_METRICS = ["persona_consistency", "style_similarity", "relevance", "context_consistency"]
CAPTAIN_SCORE_WEIGHTS = {
    "persona_consistency": 0.45,
    "style_similarity": 0.35,
    "relevance": 0.20,
}

# A/B column prefixes in CSV
AB_PREFIXES = ["A_", "B_"]


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------
def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def std(values: list[float]) -> float:
    if len(values) < 2:
        return float("nan")
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def weighted_kappa_quadratic(rater1: list[int], rater2: list[int], n_categories: int = 5) -> float:
    """Compute quadratic weighted Cohen's Kappa for two raters."""
    n = len(rater1)
    if n == 0:
        return float("nan")

    weights = [[0.0] * n_categories for _ in range(n_categories)]
    for i in range(n_categories):
        for j in range(n_categories):
            weights[i][j] = ((i - j) ** 2) / ((n_categories - 1) ** 2)

    # Observed matrix
    obs = [[0] * n_categories for _ in range(n_categories)]
    for r1, r2 in zip(rater1, rater2):
        r1_idx, r2_idx = r1 - 1, r2 - 1
        if 0 <= r1_idx < n_categories and 0 <= r2_idx < n_categories:
            obs[r1_idx][r2_idx] += 1

    # Marginals
    row_marginals = [sum(obs[i]) / n for i in range(n_categories)]
    col_marginals = [sum(obs[i][j] for i in range(n_categories)) / n for j in range(n_categories)]

    # Expected matrix
    exp = [[row_marginals[i] * col_marginals[j] for j in range(n_categories)] for i in range(n_categories)]

    po = sum(weights[i][j] * obs[i][j] / n for i in range(n_categories) for j in range(n_categories))
    pe = sum(weights[i][j] * exp[i][j] for i in range(n_categories) for j in range(n_categories))

    if pe <= 1e-12:
        return 1.0 if po <= 1e-12 else 0.0
    if pe >= 1.0:
        return 0.0
    return 1.0 - po / pe


def krippendorff_alpha_interval(data: list[list[float | None]]) -> float:
    """
    Compute Krippendorff's Alpha using squared interval distance.
    data[rater_idx][item_idx] = score or None
    """
    n_raters = len(data)
    if n_raters < 2:
        return float("nan")
    n_items = len(data[0])

    def pairable_pairs(item_idx):
        vals = [data[r][item_idx] for r in range(n_raters) if data[r][item_idx] is not None]
        return vals

    # Observed disagreement
    do = 0.0
    n_pairs = 0
    for i in range(n_items):
        vals = pairable_pairs(i)
        m = len(vals)
        if m < 2:
            continue
        for u in range(m):
            for v in range(u + 1, m):
                do += (vals[u] - vals[v]) ** 2
                n_pairs += 1

    if n_pairs == 0:
        return float("nan")
    do = do / n_pairs

    # All values for expected disagreement
    all_vals = [v for i in range(n_items) for v in pairable_pairs(i)]
    total = len(all_vals)
    if total < 2:
        return float("nan")
    de = sum((all_vals[i] - all_vals[j]) ** 2 for i in range(total) for j in range(i + 1, total))
    de = de / (total * (total - 1) / 2)

    if de == 0:
        return 1.0
    return 1.0 - do / de


def wilcoxon_signed_rank(x: list[float], y: list[float]) -> dict:
    """
    Two-sided Wilcoxon Signed-Rank Test (x vs y).
    Returns statistic, p_value, n, and interpretation.
    Uses the exact conditional sign-permutation distribution of the observed
    signed ranks. Average ranks are scaled by two so tied ranks remain exact.
    """
    if len(x) != len(y):
        return {"error": "mismatched lengths"}
    diffs = [xi - yi for xi, yi in zip(x, y) if xi != yi]
    n = len(diffs)
    if n < 5:
        return {
            "n_pairs": n,
            "statistic": None,
            "p_value": None,
            "note": "Too few pairs for reliable test (n < 5). Report descriptively only.",
        }

    abs_diffs = sorted(enumerate(diffs), key=lambda t: abs(t[1]))
    # Assign ranks (1-indexed), averaging ties
    ranked = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and abs(abs_diffs[j + 1][1]) == abs(abs_diffs[j][1]):
            j += 1
        rank_avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranked[abs_diffs[k][0]] = rank_avg
        i = j + 1

    w_plus = sum(ranked[i] for i, d in enumerate(diffs) if d > 0)
    w_minus = sum(ranked[i] for i, d in enumerate(diffs) if d < 0)
    statistic = min(w_plus, w_minus)

    scaled_ranks = [int(round(rank * 2)) for rank in ranked]
    scaled_cutoff = int(round(statistic * 2))
    distribution = [0] * (sum(scaled_ranks) + 1)
    distribution[0] = 1
    highest_sum = 0
    for rank in scaled_ranks:
        for rank_sum in range(highest_sum, -1, -1):
            if distribution[rank_sum]:
                distribution[rank_sum + rank] += distribution[rank_sum]
        highest_sum += rank

    lower_tail_count = sum(distribution[: scaled_cutoff + 1])
    p_value = min(1.0, 2.0 * lower_tail_count / (2**n))
    rank_biserial = (w_plus - w_minus) / (w_plus + w_minus)

    alpha = 0.05
    significant = p_value < alpha
    p_value_display = "<0.0001" if p_value < 0.0001 else f"{p_value:.4f}"
    return {
        "n_pairs": n,
        "W_plus": round(w_plus, 1),
        "W_minus": round(w_minus, 1),
        "statistic": round(statistic, 1),
        "p_value": p_value,
        "p_value_display": p_value_display,
        "method": "exact sign-permutation",
        "rank_biserial_correlation": round(rank_biserial, 4),
        "significant_at_0.05": significant,
        "interpretation": (
            f"Significant difference (p{p_value_display if p_value_display.startswith('<') else '=' + p_value_display})"
            if significant
            else f"No significant difference (p={p_value_display} >= 0.05)"
        ),
    }


def interpret_kappa(k: float) -> str:
    if math.isnan(k):
        return "N/A"
    if k < 0:
        return "Poor (worse than chance)"
    if k < 0.20:
        return "Slight"
    if k < 0.40:
        return "Fair"
    if k < 0.60:
        return "Moderate"
    if k < 0.80:
        return "Substantial"
    return "Almost perfect"


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------
def load_scored_csv(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def parse_score(val: str) -> float | None:
    """Parse a score string to float, or None if N/A or blank."""
    v = str(val).strip()
    if v.upper() in ("N/A", "", "-", "NA"):
        return None
    try:
        score = float(v)
        if 1.0 <= score <= 5.0:
            return score
        return None
    except ValueError:
        return None


def extract_scores(
    rows: list[dict],
    is_ab: bool,
    ab_mapping: dict[str, dict] | None = None,
) -> dict:
    """
    Extract per-model scores keyed by prompt ID.

    A/B assignments are randomized per prompt, so blind column labels must be
    resolved through the private mapping before scores are aggregated.
    """
    if is_ab:
        if not ab_mapping:
            raise ValueError("A/B mapping is required for randomized blind evaluation.")

        scores: dict[str, dict[str, dict[str, float]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        prompt_ids = []
        for row in rows:
            pid = row.get("prompt_id", "")
            if not pid:
                continue
            assignment = ab_mapping.get(pid)
            if not assignment:
                raise ValueError(f"Missing A/B mapping for prompt_id={pid!r}")
            prompt_ids.append(pid)
            for prefix in AB_PREFIXES:
                blind_label = prefix.rstrip("_")
                model = assignment.get(blind_label, "").strip()
                if not model:
                    raise ValueError(
                        f"Missing model label for prompt_id={pid!r}, blind label={blind_label}"
                    )
                for metric in SINGLE_TURN_METRICS:
                    col = f"{prefix}{metric}"
                    score = parse_score(row.get(col, ""))
                    if score is not None:
                        scores[model][metric][pid] = score
                # Context Consistency
                col = f"{prefix}context_consistency"
                score = parse_score(row.get(col, ""))
                if score is not None:
                    scores[model]["context_consistency"][pid] = score
        result = {
            model: {metric: dict(values) for metric, values in metrics.items()}
            for model, metrics in scores.items()
        }
        result["prompt_ids"] = prompt_ids
        return result
    else:
        scores: dict[str, dict[str, dict[str, float]]] = {
            "model": defaultdict(dict)
        }
        prompt_ids = []
        for row in rows:
            pid = row.get("prompt_id", "")
            if not pid:
                continue
            prompt_ids.append(pid)
            for metric in SINGLE_TURN_METRICS:
                score = parse_score(row.get(metric, ""))
                if score is not None:
                    scores["model"][metric][pid] = score
            score = parse_score(row.get("context_consistency", ""))
            if score is not None:
                scores["model"]["context_consistency"][pid] = score
        return {
            "model": {
                metric: dict(values)
                for metric, values in scores["model"].items()
            },
            "prompt_ids": prompt_ids,
        }


def paired_prompt_means(
    all_rater_data: list[dict],
    model_a: str,
    model_b: str,
    metric: str,
) -> tuple[list[float], list[float]]:
    """Average paired rater scores per prompt before model comparison."""
    prompt_ids = sorted({
        pid
        for rater_data in all_rater_data
        for pid in (
            set(rater_data.get(model_a, {}).get(metric, {}))
            & set(rater_data.get(model_b, {}).get(metric, {}))
        )
    })
    model_a_means = []
    model_b_means = []
    for pid in prompt_ids:
        paired_scores = []
        for rater_data in all_rater_data:
            scores_a = rater_data.get(model_a, {}).get(metric, {})
            scores_b = rater_data.get(model_b, {}).get(metric, {})
            if pid in scores_a and pid in scores_b:
                paired_scores.append((scores_a[pid], scores_b[pid]))
        if paired_scores:
            model_a_means.append(mean([pair[0] for pair in paired_scores]))
            model_b_means.append(mean([pair[1] for pair in paired_scores]))
    return model_a_means, model_b_means


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze human evaluation results for MiniMe.")
    parser.add_argument("--run-dir", required=True,
                        help="Run dir under reports/evaluation/")
    parser.add_argument("--eval-csvs", nargs="+", required=True,
                        help="Scored CSV files from evaluators (one per evaluator)")
    parser.add_argument("--single-model", action="store_true",
                        help="Single model evaluation (no A/B columns)")
    parser.add_argument("--labels", nargs=2, default=None,
                        help="Preferred output order for the two actual model labels. "
                             "The per-prompt private mapping is still required.")
    return parser.parse_args()


def load_ab_mapping(run_dir: Path) -> dict[str, dict]:
    """Load A/B assignment mapping from private mapping file."""
    mapping_file = run_dir / "human_eval_mapping_private.txt"
    if not mapping_file.exists():
        return {}
    mapping = {}
    in_mapping = False
    with mapping_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "A/B Assignment Mapping" in line:
                in_mapping = True
                continue
            if in_mapping and ": A=" in line:
                parts = line.split(": A=")
                pid = parts[0].strip()
                rest = parts[1].split(", B=")
                mapping[pid] = {"A": rest[0].strip(), "B": rest[1].strip() if len(rest) > 1 else ""}
    return mapping


def main() -> None:
    args = parse_args()
    run_dir = REPORTS_BASE / args.run_dir
    if not run_dir.exists():
        print(f"[ERROR] Run dir not found: {run_dir}")
        sys.exit(1)

    is_ab = not args.single_model
    ab_mapping = load_ab_mapping(run_dir) if is_ab else {}
    if is_ab and not ab_mapping:
        print("[ERROR] A/B mapping not found or empty. Cannot unblind randomized assignments safely.")
        sys.exit(1)

    print(f"Mode      : {'A/B comparison' if is_ab else 'Single model'}")
    print(f"Evaluators: {len(args.eval_csvs)}")

    all_rater_data = []
    for csv_path_str in args.eval_csvs:
        csv_path = Path(csv_path_str)
        if not csv_path.exists():
            # Try relative to run_dir
            csv_path = run_dir / csv_path_str
        if not csv_path.exists():
            print(f"[WARN] CSV not found: {csv_path_str}")
            continue
        rows = load_scored_csv(csv_path)
        try:
            extracted = extract_scores(rows, is_ab, ab_mapping)
        except ValueError as exc:
            print(f"[ERROR] {csv_path.name}: {exc}")
            sys.exit(1)
        all_rater_data.append(extracted)
        print(f"Loaded: {csv_path.name} ({len(rows)} rows)")

    if not all_rater_data:
        print("[ERROR] No valid evaluator CSVs loaded.")
        sys.exit(1)

    # Aggregate scores per model per metric across all raters
    discovered_models = {
        key
        for rater_data in all_rater_data
        for key in rater_data
        if key != "prompt_ids"
    }
    model_keys = sorted(discovered_models)
    if args.labels:
        preferred = [label for label in args.labels if label in discovered_models]
        model_keys = preferred + [label for label in model_keys if label not in preferred]

    results = {}
    for model_key in model_keys:
        results[model_key] = {}
        for metric in ALL_METRICS:
            all_scores = []
            for rater_data in all_rater_data:
                scores = rater_data.get(model_key, {}).get(metric, {})
                all_scores.extend(scores.values())
            if all_scores:
                results[model_key][metric] = {
                    "n": len(all_scores),
                    "mean": round(mean(all_scores), 3),
                    "sd": round(std(all_scores), 3),
                    "min": min(all_scores),
                    "max": max(all_scores),
                }

    captain_scores = {}
    for model_key in model_keys:
        weighted_sum = 0.0
        total_weight = 0.0
        metric_ns = []
        for metric, weight in CAPTAIN_SCORE_WEIGHTS.items():
            data = results.get(model_key, {}).get(metric)
            if not data:
                continue
            weighted_sum += data["mean"] * weight
            total_weight += weight
            metric_ns.append(data["n"])
        if total_weight:
            captain_scores[model_key] = {
                "score": round(weighted_sum / total_weight, 3),
                "n": min(metric_ns) if metric_ns else 0,
                "weights": CAPTAIN_SCORE_WEIGHTS,
            }

    # Inter-rater agreement (Weighted Kappa per pair, Krippendorff's Alpha)
    agreement = {}
    if len(all_rater_data) >= 2:
        for metric in ALL_METRICS:
            kappas = []
            kappas_by_model = {model_key: [] for model_key in model_keys}
            # Pairwise Weighted Kappa
            for i in range(len(all_rater_data)):
                for j in range(i + 1, len(all_rater_data)):
                    for model_key in model_keys:
                        s1 = all_rater_data[i].get(model_key, {}).get(metric, {})
                        s2 = all_rater_data[j].get(model_key, {}).get(metric, {})
                        common_prompts = sorted(set(s1) & set(s2))
                        if len(common_prompts) >= 5:
                            k = weighted_kappa_quadratic(
                                [int(s1[pid]) for pid in common_prompts],
                                [int(s2[pid]) for pid in common_prompts],
                            )
                            kappas.append(k)
                            kappas_by_model[model_key].append(k)

            # Krippendorff's Alpha is computed per model. Pooling models would
            # inflate expected disagreement when their score distributions differ.
            alpha_by_model = {}
            for model_key in model_keys:
                agreement_items = sorted({
                    pid
                    for rater_data in all_rater_data
                    for pid in rater_data.get(model_key, {}).get(metric, {})
                })
                kripp_data = [
                    [
                        rater_data.get(model_key, {}).get(metric, {}).get(pid)
                        for pid in agreement_items
                    ]
                    for rater_data in all_rater_data
                ]
                alpha = (
                    krippendorff_alpha_interval(kripp_data)
                    if agreement_items
                    else float("nan")
                )
                alpha_by_model[model_key] = (
                    round(alpha, 4) if not math.isnan(alpha) else "N/A"
                )
            mean_kappa = mean([k for k in kappas if not math.isnan(k)]) if kappas else float("nan")
            model_kappas = {}
            for model_key, values in kappas_by_model.items():
                valid_values = [value for value in values if not math.isnan(value)]
                model_kappas[model_key] = (
                    round(mean(valid_values), 4) if valid_values else "N/A"
                )

            agreement[metric] = {
                "mean_weighted_kappa_quadratic": round(mean_kappa, 4) if not math.isnan(mean_kappa) else "N/A",
                "weighted_kappa_by_model": model_kappas,
                "kappa_interpretation": interpret_kappa(mean_kappa),
                "krippendorff_alpha_by_model": alpha_by_model,
                "krippendorff_metric": "interval",
                "n_evaluator_pairs": len(all_rater_data) * (len(all_rater_data) - 1) // 2,
                "n_model_pair_comparisons": len(kappas),
            }

    # Wilcoxon test for A/B comparison
    wilcoxon_results = {}
    if is_ab and len(model_keys) == 2:
        mk_a, mk_b = model_keys[0], model_keys[1]
        for metric in ALL_METRICS:
            scores_a_all, scores_b_all = paired_prompt_means(
                all_rater_data, mk_a, mk_b, metric
            )
            if scores_a_all and scores_b_all:
                wilcoxon_results[metric] = wilcoxon_signed_rank(scores_a_all, scores_b_all)

    # Win rate (A/B)
    win_rate = {}
    if is_ab and len(model_keys) == 2:
        mk_a, mk_b = model_keys[0], model_keys[1]
        for metric in SINGLE_TURN_METRICS:
            wins_a, wins_b, ties = 0, 0, 0
            scores_a, scores_b = paired_prompt_means(
                all_rater_data, mk_a, mk_b, metric
            )
            for value_a, value_b in zip(scores_a, scores_b):
                if value_a > value_b:
                    wins_a += 1
                elif value_b > value_a:
                    wins_b += 1
                else:
                    ties += 1
            total = wins_a + wins_b + ties
            win_rate[metric] = {
                f"{mk_a}_wins": wins_a,
                f"{mk_b}_wins": wins_b,
                "ties": ties,
                "total_comparisons": total,
                f"{mk_a}_win_rate": round(wins_a / total, 4) if total else 0,
                f"{mk_b}_win_rate": round(wins_b / total, 4) if total else 0,
            }

    # Save JSON
    output = {
        "run_dir": str(run_dir),
        "n_evaluators": len(all_rater_data),
        "mode": "A/B" if is_ab else "single",
        "scores": results,
        "captain_similarity_score": captain_scores,
        "inter_rater_agreement": agreement,
        "wilcoxon_tests": wilcoxon_results,
        "win_rate": win_rate,
    }
    json_path = run_dir / "human_eval_results.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Build Markdown
    md_lines = ["# Human Evaluation Results", "", f"Run: `{run_dir.name}`", ""]

    if captain_scores:
        md_lines += [
            "## Primary Captain Similarity Score",
            "",
            "Primary score for this project: `0.45 * persona_consistency + 0.35 * style_similarity + 0.20 * relevance`.",
            "This keeps the main judgment focused on whether the reply feels like Kappitan while still requiring the answer to fit the prompt.",
            "",
            "| Model | Score | N |",
            "| --- | ---: | ---: |",
        ]
        for mk in model_keys:
            score = captain_scores.get(mk)
            if score:
                md_lines.append(f"| `{mk}` | {score['score']:.2f} | {score['n']} |")
        md_lines.append("")

    # Scores table
    md_lines += ["## Mean Scores (1–5 scale)", ""]
    metric_labels = {
        "persona_consistency": "Persona Consistency",
        "style_similarity": "Style Similarity",
        "relevance": "Relevance",
        "context_consistency": "Context Consistency (multi-turn only)",
    }
    header = "| Metric |" + "".join(f" `{mk}` (mean ± SD; N) |" for mk in model_keys)
    sep = "| --- |" + " ---: |" * len(model_keys)
    md_lines += [header, sep]
    for metric, label in metric_labels.items():
        row = f"| {label} |"
        for mk in model_keys:
            data = results.get(mk, {}).get(metric)
            if data:
                row += f" {data['mean']:.2f} ± {data['sd']:.2f}; N={data['n']} |"
            else:
                row += " — |"
        md_lines.append(row)
    md_lines.append("")

    # Win rate
    if win_rate:
        mk_a, mk_b = model_keys[0], model_keys[1]
        md_lines += ["## Win Rate Analysis", ""]
        md_lines += [f"| Metric | `{mk_a}` wins | `{mk_b}` wins | Ties | `{mk_a}` rate |",
                     "| --- | ---: | ---: | ---: | ---: |"]
        for metric, wr in win_rate.items():
            md_lines.append(
                f"| {metric_labels.get(metric, metric)} "
                f"| {wr[f'{mk_a}_wins']} "
                f"| {wr[f'{mk_b}_wins']} "
                f"| {wr['ties']} "
                f"| {wr[f'{mk_a}_win_rate']:.2%} |"
            )
        md_lines.append("")

    # Statistical tests
    if wilcoxon_results:
        md_lines += ["## Wilcoxon Signed-Rank Test (paired models)", ""]
        md_lines += [f"> Testing paired `{model_keys[0]}` and `{model_keys[1]}` scores",
                     "> using per-prompt means aggregated across evaluators and exact sign-permutation p-values.",
                     f"> Positive rank-biserial r favors `{model_keys[0]}`.", ""]
        md_lines += ["| Metric | N pairs | W stat | Rank-biserial r | p-value | Significant | Interpretation |",
                     "| --- | ---: | ---: | ---: | ---: | --- | --- |"]
        for metric, wtest in wilcoxon_results.items():
            if "error" in wtest or wtest.get("statistic") is None:
                md_lines.append(
                    f"| {metric_labels.get(metric, metric)} | — | — | — | — | — | {wtest.get('note', '')} |"
                )
            else:
                sig = "✅ Yes" if wtest["significant_at_0.05"] else "❌ No"
                p_display = wtest.get("p_value_display", f"{wtest['p_value']:.4f}")
                md_lines.append(
                    f"| {metric_labels.get(metric, metric)} "
                    f"| {wtest['n_pairs']} "
                    f"| {wtest['statistic']} "
                    f"| {wtest['rank_biserial_correlation']:.4f} "
                    f"| {p_display} "
                    f"| {sig} "
                    f"| {wtest['interpretation']} |"
                )
        md_lines.append("")

    # Inter-rater agreement
    if agreement:
        md_lines += ["## Inter-Rater Agreement", ""]
        md_lines += ["> Weighted Kappa (Quadratic) is appropriate for ordinal 1-5 scale.",
                     "> Agreement is calculated separately per model; Alpha uses interval distance.", ""]
        md_lines += ["| Metric | Weighted κ by model | Mean κ | Interpretation | Krippendorff's α by model (interval) |",
                     "| --- | --- | ---: | --- | --- |"]
        for metric, ag in agreement.items():
            kappa_text = "; ".join(
                f"{model}={value}"
                for model, value in ag["weighted_kappa_by_model"].items()
            )
            alpha_text = "; ".join(
                f"{model}={value}"
                for model, value in ag["krippendorff_alpha_by_model"].items()
            )
            md_lines.append(
                f"| {metric_labels.get(metric, metric)} "
                f"| {kappa_text} "
                f"| {ag['mean_weighted_kappa_quadratic']} "
                f"| {ag['kappa_interpretation']} "
                f"| {alpha_text} |"
            )
        md_lines.append("")
        md_lines += ["> **Kappa interpretation guide:** < 0.20 = Slight | 0.20-0.40 = Fair | "
                     "0.40-0.60 = Moderate | 0.60-0.80 = Substantial | > 0.80 = Almost perfect", ""]

    md_lines += [
        "---",
        f"*Analyzed {len(all_rater_data)} evaluator(s). "
        "Statistical tests are two-sided Wilcoxon Signed-Rank (non-parametric, appropriate for ordinal data).*",
        f"*Evaluator count: n={len(all_rater_data)}. Interpret statistical power in light of the final sample size.*",
    ]

    md_path = run_dir / "human_eval_summary.md"
    with md_path.open("w", encoding="utf-8-sig") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\nSaved: {json_path}")
    print(f"Saved: {md_path}")
    print("\nKey Results:")
    if captain_scores:
        print("  Captain Similarity Score:")
        for mk in model_keys:
            score = captain_scores.get(mk)
            if score:
                print(f"    [{mk}] {score['score']:.2f}")
    for mk in model_keys:
        for metric in SINGLE_TURN_METRICS:
            data = results.get(mk, {}).get(metric)
            if data:
                print(f"  [{mk}] {metric}: {data['mean']:.2f} ± {data['sd']:.2f}")
    if wilcoxon_results:
        print("\nWilcoxon Tests:")
        for metric, wtest in wilcoxon_results.items():
            if "interpretation" in wtest:
                print(f"  {metric}: {wtest['interpretation']}")


if __name__ == "__main__":
    main()
