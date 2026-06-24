"""
Aggregate scored live-chat evaluation CSVs.

Usage:
  python evaluation/analyze_live_chat.py --run-dir 20260616-141015 \
      --eval-csvs live_rater1.csv live_rater2.csv live_rater3.csv

The script validates all rows before writing any result files.
"""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minime_core.runtime_env import configure_utf8

configure_utf8()

REPORTS_BASE = ROOT / "reports" / "evaluation"
SCORE_COLUMNS = ["captain_similarity", "context_following", "problem_level"]
COUNT_COLUMNS = [
    "num_user_prompts",
    "acceptable_response_count",
    "unacceptable_response_count",
]
REQUIRED_COLUMNS = ["evaluator_id", *COUNT_COLUMNS, *SCORE_COLUMNS, "notes"]


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def sample_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    center = mean(values)
    return math.sqrt(sum((value - center) ** 2 for value in values) / (len(values) - 1))


def score_summary(values: list[float]) -> dict:
    sd = sample_std(values)
    return {
        "n": len(values),
        "mean": round(mean(values), 3),
        "sd": round(sd, 3) if sd is not None else None,
        "min": min(values),
        "max": max(values),
    }


def parse_integer(value: str, field: str, row_ref: str, minimum: int = 0) -> int:
    text = str(value).strip()
    try:
        parsed = int(text)
    except ValueError as exc:
        raise ValueError(f"{row_ref}: {field} must be an integer, got {text!r}") from exc
    if parsed < minimum:
        raise ValueError(f"{row_ref}: {field} must be >= {minimum}, got {parsed}")
    return parsed


def parse_score(value: str, field: str, row_ref: str) -> float:
    text = str(value).strip()
    try:
        parsed = float(text)
    except ValueError as exc:
        raise ValueError(f"{row_ref}: {field} must be a number from 1 to 5, got {text!r}") from exc
    if not 1.0 <= parsed <= 5.0:
        raise ValueError(f"{row_ref}: {field} must be from 1 to 5, got {parsed}")
    return parsed


def is_blank_row(row: dict) -> bool:
    return not any(str(row.get(column, "")).strip() for column in REQUIRED_COLUMNS)


def load_live_chat_rows(paths: list[Path]) -> list[dict]:
    records = []
    errors = []

    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
            if missing:
                errors.append(f"{path.name}: missing columns: {', '.join(missing)}")
                continue

            for row_number, row in enumerate(reader, 2):
                if is_blank_row(row):
                    continue
                row_ref = f"{path.name}:{row_number}"
                try:
                    evaluator_id = str(row.get("evaluator_id", "")).strip()
                    if not evaluator_id:
                        raise ValueError(f"{row_ref}: evaluator_id is required")

                    num_prompts = parse_integer(
                        row.get("num_user_prompts", ""),
                        "num_user_prompts",
                        row_ref,
                        minimum=1,
                    )
                    acceptable_count = parse_integer(
                        row.get("acceptable_response_count", ""),
                        "acceptable_response_count",
                        row_ref,
                    )
                    unacceptable_count = parse_integer(
                        row.get("unacceptable_response_count", ""),
                        "unacceptable_response_count",
                        row_ref,
                    )
                    classified_count = acceptable_count + unacceptable_count
                    if classified_count != num_prompts:
                        raise ValueError(
                            f"{row_ref}: acceptable_response_count + "
                            f"unacceptable_response_count "
                            f"({classified_count}) must equal "
                            f"num_user_prompts ({num_prompts})"
                        )

                    scores = {
                        field: parse_score(row.get(field, ""), field, row_ref)
                        for field in SCORE_COLUMNS
                    }
                    records.append({
                        "evaluator_id": evaluator_id,
                        "num_user_prompts": num_prompts,
                        **scores,
                        "acceptable_response_count": acceptable_count,
                        "unacceptable_response_count": unacceptable_count,
                        "notes": str(row.get("notes", "")).strip(),
                        "source_file": path.name,
                        "source_row": row_number,
                    })
                except ValueError as exc:
                    errors.append(str(exc))

    if errors:
        raise ValueError("\n".join(errors))
    if not records:
        raise ValueError("No completed live-chat evaluation rows were found.")
    return records


def aggregate_records(records: list[dict]) -> dict:
    total_prompts = sum(record["num_user_prompts"] for record in records)
    total_acceptable = sum(record["acceptable_response_count"] for record in records)
    total_unacceptable = sum(record["unacceptable_response_count"] for record in records)

    session_scores = {
        field: score_summary([record[field] for record in records])
        for field in SCORE_COLUMNS
    }

    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["evaluator_id"]].append(record)

    per_evaluator = {}
    for evaluator_id, evaluator_records in sorted(grouped.items()):
        evaluator_prompts = sum(record["num_user_prompts"] for record in evaluator_records)
        evaluator_acceptable = sum(
            record["acceptable_response_count"] for record in evaluator_records
        )
        evaluator_unacceptable = sum(
            record["unacceptable_response_count"] for record in evaluator_records
        )
        per_evaluator[evaluator_id] = {
            "sessions": len(evaluator_records),
            "num_user_prompts": evaluator_prompts,
            "captain_similarity_mean": round(
                mean([record["captain_similarity"] for record in evaluator_records]), 3
            ),
            "context_following_mean": round(
                mean([record["context_following"] for record in evaluator_records]), 3
            ),
            "problem_level_mean": round(
                mean([record["problem_level"] for record in evaluator_records]), 3
            ),
            "acceptable_response_count": evaluator_acceptable,
            "unacceptable_response_count": evaluator_unacceptable,
            "acceptable_response_rate": round(
                evaluator_acceptable / evaluator_prompts, 4
            ),
            "unacceptable_response_rate": round(
                evaluator_unacceptable / evaluator_prompts, 4
            ),
        }

    evaluator_score_keys = {
        "captain_similarity": "captain_similarity_mean",
        "context_following": "context_following_mean",
        "problem_level": "problem_level_mean",
    }
    evaluator_scores = {
        field: score_summary([
            data[evaluator_score_keys[field]] for data in per_evaluator.values()
        ])
        for field in SCORE_COLUMNS
    }
    evaluator_acceptable_rates = [
        data["acceptable_response_rate"] for data in per_evaluator.values()
    ]

    return {
        "n_evaluators": len(grouped),
        "n_sessions": len(records),
        "total_user_prompts": total_prompts,
        "evaluator_scores": evaluator_scores,
        "session_scores": session_scores,
        "response_counts": {
            "acceptable": total_acceptable,
            "unacceptable": total_unacceptable,
        },
        "response_rates": {
            "acceptable": round(total_acceptable / total_prompts, 4),
            "unacceptable": round(total_unacceptable / total_prompts, 4),
        },
        "evaluator_acceptable_rate": score_summary(evaluator_acceptable_rates),
        "per_evaluator": per_evaluator,
        "records": records,
    }


def format_mean_sd(data: dict) -> str:
    if data["sd"] is None:
        return f"{data['mean']:.2f} (SD N/A)"
    return f"{data['mean']:.2f} ± {data['sd']:.2f}"


def write_outputs(run_dir: Path, result: dict) -> tuple[Path, Path]:
    json_path = run_dir / "live_chat_results.json"
    md_path = run_dir / "live_chat_summary.md"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    lines = [
        "# Live Chat Evaluation Results",
        "",
        f"Run: `{run_dir.name}`",
        "",
        "## Coverage",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
        f"| Evaluators | {result['n_evaluators']} |",
        f"| Chat sessions | {result['n_sessions']} |",
        f"| User prompts | {result['total_user_prompts']} |",
        "",
        "## Scores by Evaluator (1-5, primary)",
        "",
        "| Metric | Mean ± SD | N | Direction |",
        "| --- | ---: | ---: | --- |",
    ]
    directions = {
        "captain_similarity": "Higher is better",
        "context_following": "Higher is better",
        "problem_level": "Lower is better",
    }
    for metric in SCORE_COLUMNS:
        data = result["evaluator_scores"][metric]
        lines.append(
            f"| {metric} | {format_mean_sd(data)} | {data['n']} | {directions[metric]} |"
        )

    lines += [
        "",
        "Each evaluator contributes one mean score, so evaluators with more chat sessions do not receive extra weight.",
        "",
        "## Scores by Session (descriptive)",
        "",
        "| Metric | Mean ± SD | N | Direction |",
        "| --- | ---: | ---: | --- |",
    ]
    for metric in SCORE_COLUMNS:
        data = result["session_scores"][metric]
        lines.append(
            f"| {metric} | {format_mean_sd(data)} | {data['n']} | {directions[metric]} |"
        )

    counts = result["response_counts"]
    rates = result["response_rates"]
    lines += [
        "",
        "## Response Quality",
        "",
        "| Classification | Count | Rate |",
        "| --- | ---: | ---: |",
        f"| Acceptable | {counts['acceptable']} | {rates['acceptable']:.2%} |",
        f"| Unacceptable | {counts['unacceptable']} | {rates['unacceptable']:.2%} |",
        "",
        f"Mean acceptable rate across evaluators: {result['evaluator_acceptable_rate']['mean']:.2%} "
        f"(SD {result['evaluator_acceptable_rate']['sd']:.2%}, N={result['evaluator_acceptable_rate']['n']}).",
        "",
        "Individual evaluator scores are retained only in the private JSON/CSV artifacts and are not included in this public summary.",
    ]

    lines += [
        "",
        "---",
        "*Live-chat scores are subjective user-study results. Report the evaluator and prompt counts with all means and rates.*",
    ]
    with md_path.open("w", encoding="utf-8-sig") as file:
        file.write("\n".join(lines) + "\n")

    return json_path, md_path


def resolve_csv_paths(run_dir: Path, csv_args: list[str]) -> list[Path]:
    paths = []
    for value in csv_args:
        path = Path(value)
        if not path.exists():
            path = run_dir / value
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {value}")
        paths.append(path)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze MiniMe live-chat evaluation CSVs.")
    parser.add_argument("--run-dir", required=True, help="Run directory under reports/evaluation/")
    parser.add_argument(
        "--eval-csvs",
        nargs="+",
        required=True,
        help="Completed live-chat CSV files, one or more files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = REPORTS_BASE / args.run_dir
    if not run_dir.exists():
        print(f"[ERROR] Run dir not found: {run_dir}")
        sys.exit(1)

    try:
        csv_paths = resolve_csv_paths(run_dir, args.eval_csvs)
        records = load_live_chat_rows(csv_paths)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    result = aggregate_records(records)
    json_path, md_path = write_outputs(run_dir, result)
    print(f"Loaded {result['n_sessions']} session(s) from {result['n_evaluators']} evaluator(s)")
    print(f"Saved: {json_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
