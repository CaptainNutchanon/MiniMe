"""
evaluation/prepare_human_eval.py

Create a blind A/B evaluation CSV for human raters.

- Randomizes model label assignment (A/B) per prompt using seed=42
- Does NOT reveal which model is baseline or fine-tuned
- Creates one CSV per evaluator (or a single shared CSV)
- Multi-turn prompts: Context Consistency metric is included
- Single-turn prompts: Context Consistency column is marked N/A

Usage:
  python evaluation/prepare_human_eval.py --run-dir 20260612-163000 --labels finetuned baseline
  python evaluation/prepare_human_eval.py --run-dir 20260612-163000 --labels finetuned  # runtime-only
"""

import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minime_core.runtime_env import configure_utf8

configure_utf8()

REPORTS_BASE = ROOT / "reports" / "evaluation"
SEED = 42

# Metrics to score
# Context Consistency is only applicable for multi-turn
SINGLE_TURN_METRICS = [
    "persona_consistency",
    "style_similarity",
    "relevance",
]
MULTI_TURN_METRICS = [
    "persona_consistency",
    "style_similarity",
    "relevance",
    "context_consistency",
]
MULTI_TURN_CATEGORY = "multi_turn"

RUBRIC = {
    "persona_consistency": "บุคลิก/ตัวตนตรงกับกัปปิตันไหม (1=ไม่เหมือนเลย 5=แยกไม่ออกว่าเป็น AI)",
    "style_similarity": "ภาษา น้ำเสียง คำแสลง ความยาว ตรงกับกัปปิตันไหม (1=ต่างมาก 5=เหมือนกัปปิตันพิมพ์เอง)",
    "relevance": "ตอบตรงกับที่ถามไหม (1=ไม่เกี่ยวเลย 5=ตรงและสมบูรณ์)",
    "context_consistency": "[multi-turn only] คำตอบสอดคล้องกับบทสนทนาทั้งหมดไหม (1=ขัดแย้ง 5=สอดคล้องสมบูรณ์) — N/A สำหรับ single-turn",
}

RUBRIC_DETAIL = """
=== คำแนะนำสำหรับผู้ประเมิน ===

ให้คะแนน 1-5 สำหรับแต่ละ metric โดยพิจารณาจาก Response A และ Response B แยกกัน

Persona Consistency:
  1 = ไม่เหมือนกัปปิตันเลย ตอบแบบ AI ทั่วไป
  2 = มีร่องรอยบ้าง แต่ยังเป็น AI ชัด
  3 = บุคลิกใกล้เคียง แต่มีจุดผิดสังเกต 1-2 จุด
  4 = เหมือนเป็นส่วนใหญ่ มีผิดเล็กน้อย
  5 = แยกไม่ออกว่ากัปปิตันจริงหรือ AI

Style Similarity:
  1 = ภาษาต่างโดยสิ้นเชิง ยาว ทางการ ไม่มีแสลง
  2 = มีบางอย่างคล้าย แต่ awkward
  3 = สไตล์พอใช้ แต่ความยาวหรือน้ำเสียงเพี้ยน
  4 = ตรงเกือบหมด ผิดแค่ 1 มิติ
  5 = เหมือนกัปปิตันพิมพ์เองทุกองค์ประกอบ

Relevance:
  1 = ตอบไม่เกี่ยวกับคำถามเลย
  2 = เกี่ยวเล็กน้อย ไม่ตรงประเด็น
  3 = เกี่ยวข้อง แต่ไม่ครบหรือคลาดเคลื่อน
  4 = ตรงประเด็น เข้าใจ context
  5 = ตอบตรงและเหมาะสมกับ context ทุกด้าน

Context Consistency (multi-turn เท่านั้น):
  1 = ขัดแย้งกับบทสนทนาก่อนหน้า
  2 = ไม่สอดคล้องชัดเจน
  3 = สอดคล้องบ้าง แต่มีจุด inconsistent
  4 = สอดคล้องดี มีผิดเล็กน้อย
  5 = สอดคล้องสมบูรณ์ตลอดบทสนทนา

หมายเหตุ:
- ห้ามใช้ความรู้ภายนอกในการตัดสิน — ดูเฉพาะ response ที่แสดง
- ถ้า response เป็นช่องว่างหรือ [REJECTED] ให้ได้คะแนน 1 ทุก metric
- Context Consistency ให้ใส่ N/A สำหรับ single-turn prompts
"""


def format_turns_for_display(turns: list[dict]) -> str:
    """Format conversation turns for human display."""
    lines = []
    for t in turns:
        role_label = "👤 User" if t["role"] == "user" else "🤖 Assistant"
        lines.append(f"{role_label}: {t['content']}")
    return " | ".join(lines)


def load_responses(run_dir: Path, label: str) -> dict[str, dict]:
    """Load responses for a label, keyed by prompt_id."""
    path = run_dir / f"responses_{label}.jsonl"
    if not path.exists():
        return {}
    results = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                results[r["prompt_id"]] = r
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare blind human evaluation CSV.")
    parser.add_argument("--run-dir", required=True,
                        help="Run dir under reports/evaluation/")
    parser.add_argument("--labels", nargs="+", default=None,
                        help="Exactly 2 model labels for A/B comparison, or 1 label for single-model eval")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = REPORTS_BASE / args.run_dir
    if not run_dir.exists():
        print(f"[ERROR] Run dir not found: {run_dir}")
        sys.exit(1)

    # Discover labels if not specified
    if args.labels:
        labels = args.labels
    else:
        found = sorted(p.stem.replace("responses_", "") for p in run_dir.glob("responses_*.jsonl"))
        if not found:
            print(f"[ERROR] No responses_*.jsonl found in {run_dir}")
            sys.exit(1)
        labels = found
        print(f"Auto-detected labels: {labels}")

    if len(labels) > 2:
        print(f"[ERROR] At most 2 labels supported for A/B blind eval. Got: {labels}")
        sys.exit(1)

    responses_by_label = {label: load_responses(run_dir, label) for label in labels}
    for label, results in responses_by_label.items():
        print(f"Loaded {len(results)} responses for '{label}'")

    # Get all prompt_ids (union across labels)
    all_prompt_ids = sorted(
        set().union(*[set(r.keys()) for r in responses_by_label.values()])
    )

    # Randomize A/B assignments — reproducible with seed 42
    rng = random.Random(SEED)
    ab_assignment: dict[str, dict] = {}  # prompt_id -> {"A": label, "B": label}

    if len(labels) == 2:
        label_a, label_b = labels
        for pid in all_prompt_ids:
            if rng.random() < 0.5:
                ab_assignment[pid] = {"A": label_a, "B": label_b}
            else:
                ab_assignment[pid] = {"A": label_b, "B": label_a}
    else:
        # Single model — no A/B, just score the one model
        label_only = labels[0]
        for pid in all_prompt_ids:
            ab_assignment[pid] = {"A": label_only}

    # Build rows
    is_ab = len(labels) == 2
    rows = []
    for pid in all_prompt_ids:
        assignment = ab_assignment[pid]
        # Pull a sample result to get turns/category
        sample_result = None
        for label in labels:
            if pid in responses_by_label[label]:
                sample_result = responses_by_label[label][pid]
                break
        if sample_result is None:
            continue

        category = sample_result.get("category", "")
        turns = sample_result.get("turns", [])
        is_multi = category == MULTI_TURN_CATEGORY
        metrics = MULTI_TURN_METRICS if is_multi else SINGLE_TURN_METRICS

        # Format conversation context (all turns except final user message for display)
        context_display = format_turns_for_display(turns[:-1]) if len(turns) > 1 else ""
        final_user = turns[-1]["content"] if turns else ""

        row_base = {
            "prompt_id": pid,
            "category": category,
            "is_multi_turn": "Yes" if is_multi else "No",
            "conversation_context": context_display,
            "final_user_message": final_user,
        }

        if is_ab:
            # A/B columns
            resp_a = responses_by_label[assignment["A"]].get(pid, {})
            resp_b = responses_by_label[assignment["B"]].get(pid, {})
            reply_a = resp_a.get("final_reply", "[REJECTED]") or "[REJECTED]"
            reply_b = resp_b.get("final_reply", "[REJECTED]") or "[REJECTED]"

            for metric in SINGLE_TURN_METRICS:
                row_base[f"A_{metric}"] = ""  # evaluator fills in
                row_base[f"B_{metric}"] = ""
            if is_multi:
                row_base["A_context_consistency"] = ""
                row_base["B_context_consistency"] = ""
            else:
                row_base["A_context_consistency"] = "N/A"
                row_base["B_context_consistency"] = "N/A"

            row_base["response_A"] = reply_a
            row_base["response_B"] = reply_b
            row_base["evaluator_notes"] = ""
        else:
            # Single model columns
            resp = responses_by_label[labels[0]].get(pid, {})
            reply = resp.get("final_reply", "[REJECTED]") or "[REJECTED]"
            for metric in SINGLE_TURN_METRICS:
                row_base[f"{metric}"] = ""
            if is_multi:
                row_base["context_consistency"] = ""
            else:
                row_base["context_consistency"] = "N/A"
            row_base["response"] = reply
            row_base["evaluator_notes"] = ""

        rows.append(row_base)

    # Write CSV
    csv_path = run_dir / "human_eval_blind.csv"
    if rows:
        fieldnames = list(rows[0].keys())
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # Write rubric file (SAFE to share with evaluators — no mapping info)
    rubric_path = run_dir / "human_eval_rubric.txt"
    with rubric_path.open("w", encoding="utf-8") as f:
        f.write(RUBRIC_DETAIL)

    # Write private mapping file (NEVER share with evaluators until after scoring)
    mapping_path = run_dir / "human_eval_mapping_private.txt"
    with mapping_path.open("w", encoding="utf-8") as f:
        f.write("=== A/B Assignment Mapping (PRIVATE) ===\n")
        f.write("DO NOT share this file with evaluators until AFTER all scoring is complete.\n")
        f.write("This file reveals which model is A and which is B for each prompt.\n\n")
        if is_ab:
            for pid, assignment in ab_assignment.items():
                f.write(f"{pid}: A={assignment['A']}, B={assignment['B']}\n")
        f.write(f"\nSeed used: {SEED}\n")

    # Write instructions markdown
    instructions_path = run_dir / "human_eval_instructions.md"
    with instructions_path.open("w", encoding="utf-8") as f:
        f.write("# Human Evaluation Instructions\n\n")
        f.write("## ไฟล์ที่ต้องใช้\n\n")
        f.write("- เปิด `human_eval_blind.csv` เพื่อให้คะแนน\n")
        f.write("- เปิด `human_eval_rubric.txt` เพื่อดูเกณฑ์คะแนน 1-5\n")
        f.write("- ห้ามเปิดหรือส่งต่อ `human_eval_mapping_private.txt` ระหว่างประเมิน เพราะไฟล์นั้นเฉลยว่า A/B คือ model ไหน\n\n")
        f.write("## ต้องอ่าน column ไหนบ้าง\n\n")
        f.write("- `prompt_id`: รหัสข้อ ใช้สำหรับอ้างอิง ไม่ต้องแก้\n")
        f.write("- `category`: หมวดของ prompt ไม่ต้องแก้\n")
        f.write("- `is_multi_turn`: ถ้าเป็น `Yes` ให้ดูบทสนทนาก่อนหน้าด้วย\n")
        f.write("- `conversation_context`: ข้อความก่อนหน้าในบทสนทนา ถ้าว่างแปลว่าเป็นคำถามเดี่ยว\n")
        f.write("- `final_user_message`: ข้อความล่าสุดของ user ที่ AI ต้องตอบ\n")
        if is_ab:
            f.write("- `response_A` และ `response_B`: คำตอบจาก AI สองตัว ให้ให้คะแนนแยกกัน\n\n")
            f.write("## ต้องกรอกคะแนนช่องไหน\n\n")
            f.write("ให้ใส่ตัวเลข 1-5 ในช่องต่อไปนี้เท่านั้น:\n\n")
            f.write("- `A_persona_consistency`, `A_style_similarity`, `A_relevance`\n")
            f.write("- `B_persona_consistency`, `B_style_similarity`, `B_relevance`\n")
            f.write("- ถ้า `is_multi_turn = Yes` ให้กรอก `A_context_consistency` และ `B_context_consistency` ด้วย\n")
            f.write("- ถ้า `is_multi_turn = No` ช่อง context consistency จะเป็น `N/A` อยู่แล้ว ไม่ต้องแก้\n")
        else:
            f.write("- `response`: คำตอบจาก AI ที่ต้องให้คะแนน\n\n")
            f.write("## ต้องกรอกคะแนนช่องไหน\n\n")
            f.write("ให้ใส่ตัวเลข 1-5 ในช่องต่อไปนี้เท่านั้น:\n\n")
            f.write("- `persona_consistency`: เหมือนตัวตน/บุคลิกกัปปิตันไหม\n")
            f.write("- `style_similarity`: สไตล์ภาษา น้ำเสียง ความสั้น คำพูด เหมือนกัปปิตันไหม\n")
            f.write("- `relevance`: ตอบตรงกับ `final_user_message` ไหม\n")
            f.write("- `context_consistency`: กรอกเฉพาะแถวที่ `is_multi_turn = Yes`; ถ้าเป็น `N/A` ไม่ต้องแก้\n")
        f.write("- `evaluator_notes`: ใส่หรือไม่ใส่ก็ได้ ใช้จดเหตุผลสั้น ๆ เช่น `ตอบไม่ตรง`, `ยาวไป`, `เหมือนมาก`\n\n")
        f.write("## วิธีให้คะแนน\n\n")
        f.write("- คะแนนต้องเป็นเลข 1, 2, 3, 4 หรือ 5 เท่านั้น\n")
        f.write("- 1 = แย่มาก / ไม่เหมือน / ไม่ตรงคำถาม\n")
        f.write("- 3 = พอใช้ / กึ่ง ๆ / มีบางส่วนตรง\n")
        f.write("- 5 = ดีมาก / เหมือนมาก / ตอบตรงมาก\n")
        f.write("- เป้าหมายหลักของงานนี้คือวัดว่า AI คุยเหมือนกัปปิตันไหม จึงให้ความสำคัญกับ `persona_consistency` และ `style_similarity` มากเป็นพิเศษ\n")
        f.write("- หลังเก็บคะแนนแล้ว script จะคำนวณ `Captain Similarity Score` = 45% persona + 35% style + 20% relevance\n")
        f.write("- ถ้า response เป็น `[REJECTED]` หรือว่าง ให้คะแนน 1 ทุก metric ที่ต้องกรอก\n")
        f.write("- อย่าแก้ข้อความใน column prompt, context, user message หรือ response\n")
        f.write("- หลังให้คะแนนเสร็จ ให้บันทึกเป็นไฟล์ของตัวเอง เช่น `rater1.csv`, `rater2.csv`, `rater3.csv`\n\n")
        f.write("## ลำดับการทำ\n\n")
        f.write("1. อ่าน `human_eval_rubric.txt`\n")
        f.write("2. เปิด `human_eval_blind.csv`\n")
        f.write("3. อ่าน `conversation_context` ถ้ามี\n")
        f.write("4. อ่าน `final_user_message`\n")
        f.write("5. อ่าน response ของ AI\n")
        f.write("6. ใส่คะแนน 1-5 ในช่องคะแนนที่ระบุ\n")
        f.write("7. ทำจนครบทุก row แล้วส่งไฟล์ CSV ที่กรอกคะแนนกลับมา\n\n")
        f.write("## หมายเหตุ\n\n")
        f.write("- ไม่มีคำตอบเดียวที่ถูกเสมอ ให้ให้คะแนนจากความรู้สึกว่าเหมือนกัปปิตันและเหมาะกับบทสนทนาแค่ไหน\n")
        f.write("- ให้ประเมินจากข้อความที่เห็นในไฟล์เท่านั้น ไม่ต้องเดาว่า AI ควรรู้อะไรนอกบทสนทนา\n")
        f.write("- ถ้าคำตอบสั้นมากแต่เข้ากับสไตล์กัปปิตันและตอบตรง ให้คะแนนได้สูง\n")
        f.write("- ถ้าคำตอบมีชื่อคน สถานที่ สถานะ หรือเรื่องส่วนตัวที่ user ไม่ได้บอก ให้หัก relevance/context ตามความเหมาะสม\n\n")
        f.write(f"**ไฟล์นี้สร้างด้วย seed={SEED} — reproducible**\n")

    print(f"\nGenerated {len(rows)} evaluation rows")
    print(f"A/B mode: {'Yes — 2 models' if is_ab else 'No — single model'}")
    print(f"\nSaved:")
    print(f"  {csv_path}")
    print(f"  {rubric_path}             (share with evaluators)")
    print(f"  {instructions_path}  (share with evaluators)")
    print(f"  {mapping_path}  (DO NOT share until scoring is done)")
    print("\nNext step:")
    print("  1. Share human_eval_blind.csv + human_eval_rubric.txt + human_eval_instructions.md with 3 evaluators")
    print("  2. DO NOT share human_eval_mapping_private.txt — it reveals which model is A/B")
    print("  3. Collect scored CSVs from each evaluator")
    print(f"  4. python evaluation/analyze_human_eval.py --run-dir {args.run_dir} \\")
    print("       --eval-csvs evaluator1.csv evaluator2.csv evaluator3.csv")


if __name__ == "__main__":
    main()
