"""
evaluation/compute_metrics.py

Compute automatic metrics from generated responses and training report.

Requires at minimum one responses_<label>.jsonl in the run dir.

Usage:
  python evaluation/compute_metrics.py --run-dir 20260612-163000
  python evaluation/compute_metrics.py --run-dir 20260612-163000 --labels finetuned baseline
"""

import argparse
import importlib.util
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minime_core.runtime_env import configure_utf8
from minime_core.text_cleaning import emoji_count, is_emoji_only
from minime_core.topic_guard import garbage_reply_reason

configure_utf8()

REPORTS_BASE = ROOT / "reports" / "evaluation"
TRAINING_REPORTS_DIR = ROOT / "reports" / "training"
TRAINING_SCRIPT = ROOT / "training" / "train.py"

# Categories where we expect a persona-consistent identity response
IDENTITY_CATEGORIES = {"identity", "bot_identity"}
# Open-ended categories where generic replies should be penalized
OPEN_ENDED_CATEGORIES = {"open_ended"}

# Generic/AI-sounding replies that indicate failure
GENERIC_REPLY_RE = re.compile(
    r"(ขอโทษ|ไม่ทราบ|ไม่แน่ใจ|ไม่สามารถ|ผม|ดิฉัน|ครับ|ค่ะ|คะ|หากท่าน|ยินดี)",
    re.IGNORECASE,
)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
BAD_TOKEN_RE = re.compile(
    r"(kappitan(?:_?ton)?|kappitton|captain|kongkai|ไอแพน|คุณายาว)",
    re.IGNORECASE,
)

IDENTITY_NAME = "กัปปิตัน"
BOT_POSITIVE_RE = re.compile(r"(ใช่|ก็ประมาณ|ประมาณนั้น|ใช่ๆ|บอท|ai|เอไอ)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Distinct-N (character-level, suitable for Thai)
# ---------------------------------------------------------------------------
def char_ngrams(text: str, n: int) -> list[str]:
    """Return character n-grams, ignoring whitespace."""
    compact = re.sub(r"\s+", "", text)
    return [compact[i : i + n] for i in range(len(compact) - n + 1)]


def distinct_n(texts: list[str], n: int) -> float:
    """Compute Distinct-N across all texts (character level)."""
    all_ngrams: list[str] = []
    for t in texts:
        all_ngrams.extend(char_ngrams(t, n))
    if not all_ngrams:
        return 0.0
    return len(set(all_ngrams)) / len(all_ngrams)


# ---------------------------------------------------------------------------
# Identity accuracy
# ---------------------------------------------------------------------------
def check_identity_accuracy(result: dict) -> bool | None:
    """
    For identity prompts: did the reply contain the identity name?
    For bot_identity prompts: did the reply acknowledge being a bot/AI?
    Returns None if not an identity prompt.
    """
    cat = result.get("category", "")
    reply = result.get("final_reply", "")
    if cat == "identity":
        if not result.get("ok"):
            return False
        return IDENTITY_NAME in reply
    if cat == "bot_identity":
        if not result.get("ok"):
            return False
        return bool(BOT_POSITIVE_RE.search(reply)) and not (
            re.match(r"^\s*(?:ไม่ใช่|ไม่อะ|ไม่|ป่าว|เปล่า)\s*$", reply)
        )
    return None


# ---------------------------------------------------------------------------
# Per-result metrics
# ---------------------------------------------------------------------------
def analyze_result(result: dict) -> dict:
    reply = result.get("final_reply", "")
    raw = result.get("raw_reply", "")
    ok = result.get("ok", False)

    artifact_reason = garbage_reply_reason(raw) if raw else None
    is_artifact = artifact_reason is not None
    is_rejected = not ok
    emoji_sp = emoji_count(reply) >= 3 or is_emoji_only(reply)
    is_cjk = bool(CJK_RE.search(reply))
    is_bad_token = bool(BAD_TOKEN_RE.search(reply))
    reply_len = len(reply)
    is_long = reply_len > 70
    identity_acc = check_identity_accuracy(result)
    is_generic = (
        result.get("category") in OPEN_ENDED_CATEGORIES
        and bool(GENERIC_REPLY_RE.search(reply))
    )

    return {
        "prompt_id": result["prompt_id"],
        "category": result["category"],
        "ok": ok,
        "reply_len": reply_len,
        "is_long": is_long,
        "is_artifact": is_artifact,
        "artifact_reason": artifact_reason,
        "is_rejected": is_rejected,
        "retry_count": result.get("retry_count", 0),
        "identity_retry_reason": result.get("identity_retry_reason"),
        "is_emoji_spam": emoji_sp,
        "is_cjk": is_cjk,
        "is_bad_token": is_bad_token,
        "identity_acc": identity_acc,
        "is_generic": is_generic,
        "latency_ms": result.get("latency_ms", 0),
    }


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------
def compute_aggregate(analyses: list[dict], all_replies: list[str]) -> dict:
    n = len(analyses)
    if n == 0:
        return {}

    ok_analyses = [a for a in analyses if a["ok"]]
    ok_replies = [a for a in ok_analyses]

    reply_lens = [a["reply_len"] for a in ok_analyses] if ok_analyses else [0]
    avg_len = sum(reply_lens) / len(reply_lens) if reply_lens else 0
    median_len = sorted(reply_lens)[len(reply_lens) // 2] if reply_lens else 0

    identity_evals = [a for a in analyses if a["identity_acc"] is not None]
    identity_correct = [a for a in identity_evals if a["identity_acc"]]
    identity_acc_rate = len(identity_correct) / len(identity_evals) if identity_evals else None

    identity_retry_count = sum(1 for a in analyses if a["identity_retry_reason"])

    open_ended = [a for a in ok_analyses if a["category"] in OPEN_ENDED_CATEGORIES]
    generic_count = sum(1 for a in open_ended if a["is_generic"])
    generic_rate = generic_count / len(open_ended) if open_ended else None

    latencies = [a["latency_ms"] for a in analyses]
    avg_latency = sum(latencies) / n

    return {
        "total_prompts": n,
        "ok_count": len(ok_analyses),
        "rejected_count": n - len(ok_analyses),
        "guard_rejection_rate": round((n - len(ok_analyses)) / n, 4),
        "avg_reply_length_chars": round(avg_len, 1),
        "median_reply_length_chars": median_len,
        "long_reply_rate": round(sum(1 for a in ok_analyses if a["is_long"]) / n, 4),
        "output_artifact_rate": round(sum(1 for a in analyses if a["is_artifact"]) / n, 4),
        "emoji_spam_rate": round(sum(1 for a in ok_analyses if a["is_emoji_spam"]) / n, 4),
        "cjk_rate": round(sum(1 for a in analyses if a["is_cjk"]) / n, 4),
        "bad_token_rate": round(sum(1 for a in analyses if a["is_bad_token"]) / n, 4),
        "identity_accuracy": round(identity_acc_rate, 4) if identity_acc_rate is not None else "N/A",
        "identity_retry_rate": round(identity_retry_count / n, 4),
        "generic_reply_rate_open_ended": round(generic_rate, 4) if generic_rate is not None else "N/A",
        "avg_retry_count": round(sum(a["retry_count"] for a in analyses) / n, 3),
        "distinct_1_char": round(distinct_n(all_replies, 1), 4),
        "distinct_2_char": round(distinct_n(all_replies, 2), 4),
        "avg_latency_ms": round(avg_latency, 1),
    }


# ---------------------------------------------------------------------------
# Training report summary
# ---------------------------------------------------------------------------
def load_training_summary() -> dict | None:
    """Load the most recent training metrics JSON."""
    jsons = sorted(TRAINING_REPORTS_DIR.glob("training_metrics_*.json"), reverse=True)
    if not jsons:
        return None
    with jsons[0].open("r", encoding="utf-8") as f:
        return json.load(f)


def load_real_reply_length_reference() -> dict:
    """Load raw validation targets through the same filters used for training."""
    if not TRAINING_SCRIPT.exists():
        return {}
    spec = importlib.util.spec_from_file_location("minime_training_reference", TRAINING_SCRIPT)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sessions = module.load_jsonl_sessions(module.VAL_FILE)
    rows, _ = module.build_turn_examples(sessions)
    lengths = [len(row["messages"][-1]["content"]) for row in rows]
    if not lengths:
        return {}
    ordered = sorted(lengths)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )
    return {
        "source": str(module.VAL_FILE),
        "description": "raw validation assistant targets after training filters; curated excluded",
        "n": len(lengths),
        "mean_chars": round(sum(lengths) / len(lengths), 4),
        "median_chars": median,
        "min_chars": min(lengths),
        "max_chars": max(lengths),
    }


def training_curve_table(log_history: list[dict]) -> str:
    rows = [
        e for e in log_history
        if any(k in e for k in ("loss", "eval_loss", "train_loss"))
    ]
    lines = ["| Step | Epoch | Train Loss | Val Loss | LR |",
             "| ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        step = row.get("step", "")
        epoch = f"{row.get('epoch', ''):.3f}" if row.get("epoch") else ""
        train_l = f"{row['loss']:.4f}" if "loss" in row else (
            f"{row['train_loss']:.4f}" if "train_loss" in row else "")
        val_l = f"{row['eval_loss']:.4f}" if "eval_loss" in row else ""
        lr = f"{row['learning_rate']:.2e}" if "learning_rate" in row else ""
        lines.append(f"| {step} | {epoch} | {train_l} | {val_l} | {lr} |")
    return "\n".join(lines)


def compute_overfitting_gap(log_history: list[dict]) -> dict:
    """Compute the maximum matched train/validation loss gap."""
    train_entries = [e for e in log_history if "loss" in e and "eval_loss" not in e]
    val_entries = [e for e in log_history if "eval_loss" in e]
    if not train_entries or not val_entries:
        return {}

    matched = []
    for val_entry in val_entries:
        val_step = val_entry.get("step")
        if val_step is None:
            continue
        eligible_train = [
            entry
            for entry in train_entries
            if entry.get("step") is not None and entry["step"] <= val_step
        ]
        if not eligible_train:
            continue
        train_entry = max(eligible_train, key=lambda entry: entry["step"])
        matched.append({
            "step": val_step,
            "train_loss": train_entry["loss"],
            "val_loss": val_entry["eval_loss"],
            "gap": val_entry["eval_loss"] - train_entry["loss"],
        })

    if not matched:
        return {}
    maximum = max(matched, key=lambda item: item["gap"])
    first_overfit = next((item for item in matched if item["gap"] > 1.0), None)
    return {
        "at_step": maximum["step"],
        "train_loss": round(maximum["train_loss"], 4),
        "val_loss": round(maximum["val_loss"], 4),
        "gap": round(maximum["gap"], 4),
        "first_gap_over_1_step": first_overfit["step"] if first_overfit else None,
        "note": (
            "maximum gap > 1.0 suggests overfitting"
            if maximum["gap"] > 1.0
            else "maximum matched gap is within 1.0"
        ),
    }


# ---------------------------------------------------------------------------
# Markdown report builder
# ---------------------------------------------------------------------------
def build_markdown(
    metrics_by_label: dict[str, dict],
    analyses_by_label: dict[str, list],
    training_data: dict | None,
    reply_length_reference: dict,
    run_dir: Path,
) -> str:
    lines = ["# MiniMe Auto Evaluation Metrics", ""]
    lines.append(f"Run: `{run_dir.name}`")
    lines.append("")

    # Training summary
    if training_data:
        cfg = training_data.get("config", {})
        data = training_data.get("data", {})
        best_eval = training_data.get("best_metric")
        best_ckpt = training_data.get("best_model_checkpoint", "")
        perplexity = round(math.exp(best_eval), 2) if best_eval else "N/A"
        final_train = training_data.get("final_metrics", {}).get("train_loss")

        lines += [
            "## Training Summary (Experimental Setup)",
            "",
            "| Key | Value |",
            "| --- | --- |",
            f"| Model | `{training_data.get('model', 'N/A')}` |",
            f"| Best checkpoint | `{Path(best_ckpt).name if best_ckpt else 'N/A'}` |",
            f"| Best eval_loss | `{best_eval:.4f}` |" if best_eval else "| Best eval_loss | N/A |",
            f"| Final train_loss | `{final_train:.4f}` |" if final_train else "",
            f"| Perplexity (exp(eval_loss)) | `{perplexity}` *(reference only, not persona metric)* |",
            f"| Train examples | {data.get('final_train_examples', 'N/A')} |",
            f"| Val examples | {data.get('final_validation_examples', 'N/A')} |",
            f"| Epochs | {cfg.get('num_train_epochs', 'N/A')} |",
            f"| Max completion chars | {cfg.get('max_completion_chars', 'N/A')} |",
            "",
        ]

        overfitting = compute_overfitting_gap(training_data.get("log_history", []))
        if overfitting:
            lines += [
                "### Overfitting Analysis",
                "",
                f"Maximum matched gap at step {overfitting.get('at_step')}: "
                f"train_loss={overfitting['train_loss']}, "
                f"val_loss={overfitting['val_loss']}, "
                f"**gap={overfitting['gap']}**",
                f"*{overfitting['note']}*",
            ]
            if overfitting.get("first_gap_over_1_step") is not None:
                lines.append(
                    f"The matched gap first exceeds 1.0 at step "
                    f"{overfitting['first_gap_over_1_step']}."
                )
            lines.append("")

        log_hist = training_data.get("log_history", [])
        if log_hist:
            lines += ["### Loss Curve", "", training_curve_table(log_hist), ""]

    if reply_length_reference:
        lines += [
            "## Real Kappitan Reply-Length Reference",
            "",
            "The reference uses raw validation assistant targets after the same training filters. "
            "Curated examples are excluded. This is a corpus-level style reference, not a paired "
            "reference answer for each test prompt.",
            "",
            "| Measure | Value |",
            "| --- | ---: |",
            f"| Reference replies | {reply_length_reference['n']} |",
            f"| Mean length | {reply_length_reference['mean_chars']:.2f} chars |",
            f"| Median length | {reply_length_reference['median_chars']} chars |",
            f"| Range | {reply_length_reference['min_chars']}-{reply_length_reference['max_chars']} chars |",
            "",
        ]

    # Auto metrics per label
    lines += ["## Automatic Metrics", ""]
    for label, metrics in metrics_by_label.items():
        lines += [f"### Model: `{label}`", ""]
        lines += ["| Metric | Value |", "| --- | --- |"]
        metric_display = {
            "total_prompts": "Total prompts",
            "ok_count": "OK responses",
            "rejected_count": "Rejected (guard)",
            "guard_rejection_rate": "Guard rejection rate",
            "avg_reply_length_chars": "Avg reply length (chars)",
            "reply_length_ratio_to_real_reference": "Reply-length ratio to real reference",
            "median_reply_length_chars": "Median reply length (chars)",
            "long_reply_rate": "Long reply rate (>70 chars)",
            "output_artifact_rate": "Output artifact rate",
            "emoji_spam_rate": "Emoji spam rate",
            "cjk_rate": "CJK/weird token rate",
            "bad_token_rate": "Bad token rate",
            "identity_accuracy": "Identity accuracy",
            "identity_retry_rate": "Identity retry rate",
            "generic_reply_rate_open_ended": "Generic reply rate (open-ended)",
            "avg_retry_count": "Avg retry count",
            "distinct_1_char": "Distinct-1 (char-level)",
            "distinct_2_char": "Distinct-2 (char-level)",
            "avg_latency_ms": "Avg latency (ms)",
        }
        for key, display in metric_display.items():
            val = metrics.get(key, "N/A")
            if isinstance(val, float):
                val = f"{val:.4f}"
            lines.append(f"| {display} | {val} |")
        lines.append("")

    # Comparison table if 2 labels
    labels = list(metrics_by_label.keys())
    if len(labels) == 2:
        a, b = labels
        ma, mb = metrics_by_label[a], metrics_by_label[b]
        lines += [f"## Comparison: `{a}` vs `{b}`", ""]
        cmp_metrics = [
            ("guard_rejection_rate", "Guard rejection rate", "lower_better"),
            ("avg_reply_length_chars", "Avg reply length (chars)", "neutral"),
            ("reply_length_ratio_to_real_reference", "Reply-length ratio to real reference", "closer_to_one"),
            ("output_artifact_rate", "Output artifact rate", "lower_better"),
            ("identity_accuracy", "Identity accuracy", "higher_better"),
            ("generic_reply_rate_open_ended", "Generic reply rate", "lower_better"),
            ("distinct_1_char", "Distinct-1", "higher_better"),
            ("distinct_2_char", "Distinct-2", "higher_better"),
            ("avg_latency_ms", "Avg latency (ms)", "neutral"),
        ]
        lines.append(f"| Metric | {a} | {b} | Better |")
        lines.append("| --- | ---: | ---: | --- |")
        for key, display, direction in cmp_metrics:
            va = ma.get(key, "N/A")
            vb = mb.get(key, "N/A")
            better = ""
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                if direction == "lower_better":
                    better = a if va < vb else (b if vb < va else "tie")
                elif direction == "higher_better":
                    better = a if va > vb else (b if vb > va else "tie")
                elif direction == "closer_to_one":
                    distance_a = abs(va - 1.0)
                    distance_b = abs(vb - 1.0)
                    better = a if distance_a < distance_b else (b if distance_b < distance_a else "tie")
            va_str = f"{va:.4f}" if isinstance(va, float) else str(va)
            vb_str = f"{vb:.4f}" if isinstance(vb, float) else str(vb)
            lines.append(f"| {display} | {va_str} | {vb_str} | {better} |")
        lines.append("")

    # Per-category breakdown
    for label, analyses in analyses_by_label.items():
        lines += [f"## Per-Category Breakdown: `{label}`", ""]
        cats: dict[str, list] = {}
        for a in analyses:
            cats.setdefault(a["category"], []).append(a)
        lines += ["| Category | N | OK | Rejected | Avg Len | Identity Acc |",
                  "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for cat, items in sorted(cats.items()):
            ok = sum(1 for i in items if i["ok"])
            rejected = len(items) - ok
            ok_items = [i for i in items if i["ok"]]
            avg_l = (sum(i["reply_len"] for i in ok_items) / len(ok_items)) if ok_items else 0
            id_evals = [i for i in items if i["identity_acc"] is not None]
            id_acc = (sum(1 for i in id_evals if i["identity_acc"]) / len(id_evals)) if id_evals else None
            id_str = f"{id_acc:.2f}" if id_acc is not None else "—"
            lines.append(f"| {cat} | {len(items)} | {ok} | {rejected} | {avg_l:.1f} | {id_str} |")
        lines.append("")

    lines += [
        "---",
        "*Auto metrics report generated by `evaluation/compute_metrics.py`.*",
        "*Human evaluation scores (Persona Consistency, Style Similarity, Relevance) "
        "are separate — see `human_eval_summary.md`.*",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute automatic metrics for MiniMe evaluation.")
    parser.add_argument("--run-dir", required=True,
                        help="Run directory name under reports/evaluation/ (e.g. 20260612-163000)")
    parser.add_argument("--labels", nargs="+", default=None,
                        help="Model labels to include (default: all found in run dir)")
    parser.add_argument("--no-training", action="store_true",
                        help="Skip loading training report")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = REPORTS_BASE / args.run_dir
    if not run_dir.exists():
        print(f"[ERROR] Run dir not found: {run_dir}")
        sys.exit(1)

    # Find response files
    response_files = sorted(run_dir.glob("responses_*.jsonl"))
    if not response_files:
        print(f"[ERROR] No responses_*.jsonl found in {run_dir}")
        sys.exit(1)

    metrics_by_label: dict[str, dict] = {}
    analyses_by_label: dict[str, list] = {}

    for rf in response_files:
        label = rf.stem.replace("responses_", "")
        if args.labels and label not in args.labels:
            continue
        results = []
        with rf.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))

        analyses = [analyze_result(r) for r in results]
        ok_replies = [r["final_reply"] for r in results if r.get("ok") and r.get("final_reply")]
        metrics = compute_aggregate(analyses, ok_replies)
        metrics["label"] = label
        metrics_by_label[label] = metrics
        analyses_by_label[label] = analyses
        print(f"Loaded {len(results)} results for label '{label}'")

    training_data = None
    if not args.no_training:
        training_data = load_training_summary()
        if training_data:
            print(f"Training report: {training_data.get('timestamp')}")
        else:
            print("No training report found.")

    reply_length_reference = load_real_reply_length_reference()
    if reply_length_reference:
        reference_mean = reply_length_reference["mean_chars"]
        for metrics in metrics_by_label.values():
            metrics["reply_length_ratio_to_real_reference"] = round(
                metrics["avg_reply_length_chars"] / reference_mean,
                4,
            )
        print(
            f"Reply-length reference: {reply_length_reference['n']} real validation replies "
            f"(mean={reference_mean:.2f} chars)"
        )

    # Write JSON
    json_out = run_dir / "auto_metrics.json"
    with json_out.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "run_dir": str(run_dir),
                "metrics": metrics_by_label,
                "reply_length_reference": reply_length_reference,
                "training": {
                    "timestamp": training_data.get("timestamp") if training_data else None,
                    "model": training_data.get("model") if training_data else None,
                    "best_metric": training_data.get("best_metric") if training_data else None,
                    "best_checkpoint": training_data.get("best_model_checkpoint") if training_data else None,
                    "perplexity_reference": (
                        round(math.exp(training_data["best_metric"]), 4)
                        if training_data and training_data.get("best_metric")
                        else None
                    ),
                    "overfitting_gap": compute_overfitting_gap(
                        training_data.get("log_history", [])
                    ) if training_data else {},
                },
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # Write Markdown
    md_out = run_dir / "auto_metrics.md"
    md_content = build_markdown(
        metrics_by_label,
        analyses_by_label,
        training_data,
        reply_length_reference,
        run_dir,
    )
    with md_out.open("w", encoding="utf-8-sig") as f:
        f.write(md_content)

    print(f"\nSaved: {json_out}")
    print(f"Saved: {md_out}")
    print("\nNext step:")
    print(f"  python evaluation/prepare_human_eval.py --run-dir {args.run_dir}")


if __name__ == "__main__":
    main()
