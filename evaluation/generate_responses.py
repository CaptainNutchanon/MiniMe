"""
evaluation/generate_responses.py

Generate model responses for evaluation prompts.

Modes:
  --mode direct   Load model directly with Unsloth (for controlled baseline comparison)
  --mode runtime  Call the running web server via /api/chat/stream (measures real runtime behavior)

Usage (direct mode, fine-tuned only):
  python evaluation/generate_responses.py --adapter output/captain-lora --label finetuned

Usage (direct mode, baseline comparison):
  python evaluation/generate_responses.py --adapter output/captain-lora --label finetuned
  python evaluation/generate_responses.py --base-only --label baseline

Usage (runtime mode):
  powershell -File scripts/run_server.ps1   # start server first
  python evaluation/generate_responses.py --mode runtime --label finetuned

Usage (dry run with 5 prompts):
  python evaluation/generate_responses.py --adapter output/captain-lora --label finetuned --dry-run
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ["TOKENIZERS_PARALLELISM"] = "false"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minime_core.runtime_env import configure_utf8
from minime_core.text_cleaning import clean_generated_reply
from minime_core.topic_guard import (
    finalize_identity_reply,
    garbage_reply_reason,
    identity_policy,
    is_bot_identity_prompt,
    is_name_identity_prompt,
    needs_identity_retry,
    validate_reply,
)

configure_utf8()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROMPTS_FILE = ROOT / "evaluation" / "prompts.jsonl"
REPORTS_BASE = ROOT / "reports" / "evaluation"
MAX_SEQ_LEN = 2048
MAX_NEW_TOKENS = 24
MAX_HISTORY_MESSAGES = 6

RUNTIME_SYSTEM_PROMPT = (
    "ตอบสั้นแบบแชทไทยในสไตล์กัปปิตัน ตอบจากบทสนทนาล่าสุดเท่านั้น "
    "ถ้าขาดข้อมูลสำคัญให้ถามกลับสั้น ๆ ได้ แต่อย่าถามวนคำเดิม "
    "ห้ามเดาชื่อคน สถานที่ กิจกรรม ความสัมพันธ์ หรือสถานะของตัวเองที่ user ไม่ได้พูด"
)
GARBAGE_RETRY_SYSTEM_HINT = (
    "ตอบเป็นภาษาไทยเท่านั้น ห้ามใช้ภาษาอังกฤษหรือจีน "
    "ห้ามตอบคำประหลาด ถ้าไม่แน่ใจให้ตอบสั้น ๆ แบบแชทไทย"
)
NAME_IDENTITY_RETRY_HINT = "ถ้าผู้ใช้ถามชื่อหรือตัวตน ให้ตอบสั้น ๆ ว่า กัปปิตัน หรือ กัปปิตันก็ได้"
BOT_IDENTITY_RETRY_HINT = (
    "ถ้าผู้ใช้ถามว่าเป็น AI หรือบอท ให้ตอบสั้น ๆ เช่น ใช่ๆ หรือ ก็ประมาณนั้น "
    "ห้ามลากเรื่องเรียน งาน เกม หรือสถานที่อื่น"
)
SYSTEM_AWARE_CHAT_TEMPLATE = """{%- for message in messages %}
    {%- if message['role'] == 'system' %}
{{- '<|im_start|>system\n' + message['content'] + '<|im_end|>\n' }}
    {%- elif message['role'] == 'user' %}
{{- '<|im_start|>user\n' + message['content'] + '<|im_end|>\n' }}
    {%- elif message['role'] == 'assistant' %}
{{- '<|im_start|>assistant\n' + message['content'] + '<|im_end|>\n' }}
    {%- endif %}
{%- endfor %}
{%- if add_generation_prompt %}
{{- '<|im_start|>assistant\n' }}
{%- endif %}"""


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------
def load_prompts(path: Path) -> list[dict]:
    prompts = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                prompts.append(json.loads(line))
    return prompts


# ---------------------------------------------------------------------------
# Direct mode helpers
# ---------------------------------------------------------------------------
def build_messages_for_generation(turns: list[dict], extra_hint: str | None = None) -> list[dict]:
    """Build message list with system prompt from prompt turns."""
    system_prompt = RUNTIME_SYSTEM_PROMPT
    if extra_hint:
        system_prompt = f"{system_prompt} {extra_hint}"
    chat_turns = [t for t in turns if t["role"] in ("user", "assistant")]
    chat_turns = chat_turns[-MAX_HISTORY_MESSAGES:]
    return [{"role": "system", "content": system_prompt}, *chat_turns]


def stop_token_ids(tokenizer) -> list[int]:
    ids = []
    for tid in (tokenizer.eos_token_id, tokenizer.convert_tokens_to_ids("<|im_end|>")):
        if isinstance(tid, int) and tid >= 0 and tid not in ids:
            ids.append(tid)
    return ids


def generate_raw_reply_direct(model, tokenizer, messages: list[dict], torch_mod, *, retry: bool = False) -> str:
    encoded = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    )
    encoded = {k: v.to("cuda") for k, v in encoded.items()}
    gen_kwargs = {
        **encoded,
        "max_new_tokens": MAX_NEW_TOKENS,
        "do_sample": retry,
        "pad_token_id": tokenizer.eos_token_id,
        "eos_token_id": stop_token_ids(tokenizer),
        "repetition_penalty": 1.3,
        "no_repeat_ngram_size": 3,
    }
    if retry:
        gen_kwargs["temperature"] = 0.7
        gen_kwargs["top_p"] = 0.9
    with torch_mod.inference_mode():
        outputs = model.generate(**gen_kwargs)
    prompt_len = encoded["input_ids"].shape[-1]
    return tokenizer.decode(outputs[0][prompt_len:], skip_special_tokens=True)


def run_direct_generation(
    model,
    tokenizer,
    torch_mod,
    prompt: dict,
) -> dict:
    """Run full generation pipeline (matching server.py logic) for one prompt."""
    turns = prompt["turns"]
    user_text = turns[-1]["content"] if turns and turns[-1]["role"] == "user" else ""
    context_text = " ".join(t["content"] for t in turns[:-1] if t["role"] in ("user", "assistant"))

    messages = build_messages_for_generation(turns)

    t_start = time.perf_counter()
    raw_reply = generate_raw_reply_direct(model, tokenizer, messages, torch_mod)
    first_raw_reply = raw_reply
    retry_reason = garbage_reply_reason(raw_reply)
    initial_retry_reason = retry_reason
    retry_count = 0
    identity_retry_reason = None

    while retry_reason and retry_count < 2:
        retry_count += 1
        retry_messages = build_messages_for_generation(turns, GARBAGE_RETRY_SYSTEM_HINT)
        raw_reply = generate_raw_reply_direct(model, tokenizer, retry_messages, torch_mod, retry=True)
        retry_reason = garbage_reply_reason(raw_reply)

    clean_raw = clean_generated_reply(raw_reply)
    reply = validate_reply(user_text, context_text, raw_reply)

    if needs_identity_retry(user_text, reply):
        hint = None
        if is_name_identity_prompt(user_text):
            hint = NAME_IDENTITY_RETRY_HINT
            identity_retry_reason = "name_identity"
        elif is_bot_identity_prompt(user_text):
            hint = BOT_IDENTITY_RETRY_HINT
            identity_retry_reason = "bot_identity"
        if hint:
            retry_messages = build_messages_for_generation(turns, hint)
            raw_reply = generate_raw_reply_direct(model, tokenizer, retry_messages, torch_mod)
            retry_count += 1
            retry_reason = garbage_reply_reason(raw_reply)
            clean_raw = clean_generated_reply(raw_reply)
            reply = validate_reply(user_text, context_text, raw_reply)
    reply = finalize_identity_reply(user_text, reply)

    latency_ms = round((time.perf_counter() - t_start) * 1000, 1)
    ok = reply is not None
    guard_reason = None
    if not ok:
        guard_reason = "guard_rejected"
    elif reply != clean_raw:
        guard_reason = "sanitized"

    return {
        "prompt_id": prompt["id"],
        "category": prompt["category"],
        "turns": turns,
        "raw_reply": raw_reply,
        "final_reply": reply or "",
        "ok": ok,
        "guard_reason": guard_reason,
        "retry_count": retry_count,
        "first_raw_reply": first_raw_reply,
        "initial_garbage_reason": initial_retry_reason,
        "last_garbage_reason": retry_reason,
        "identity_retry_reason": identity_retry_reason,
        "latency_ms": latency_ms,
    }


# ---------------------------------------------------------------------------
# Runtime mode helpers
# ---------------------------------------------------------------------------
def run_runtime_generation(prompt: dict, server_url: str) -> dict:
    """Call the running server's /api/chat/stream endpoint."""
    import urllib.request

    turns = prompt["turns"]
    messages = [{"role": t["role"], "content": t["content"]} for t in turns if t["role"] in ("user", "assistant")]
    body = json.dumps({"messages": messages, "debug": True}).encode("utf-8")
    req = urllib.request.Request(
        f"{server_url}/api/chat/stream",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t_start = time.perf_counter()
    result = {
        "prompt_id": prompt["id"],
        "category": prompt["category"],
        "turns": turns,
        "raw_reply": "",
        "final_reply": "",
        "ok": False,
        "guard_reason": None,
        "retry_count": 0,
        "first_raw_reply": "",
        "initial_garbage_reason": None,
        "last_garbage_reason": None,
        "identity_retry_reason": None,
        "latency_ms": 0.0,
    }
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = json.loads(line[5:].strip())
                if "text" in data:
                    result["final_reply"] = data["text"]
                    result["ok"] = True
                # pick up debug fields from 'done' event
                for key in ("raw_reply", "first_raw_reply", "retry_count",
                            "retry_reason", "identity_retry_reason", "last_garbage_reason"):
                    if key in data:
                        result[key] = data[key]
                if "guard_reason" in data:
                    result["guard_reason"] = data["guard_reason"]
    except Exception as exc:
        result["guard_reason"] = f"request_error: {exc}"
    result["latency_ms"] = round((time.perf_counter() - t_start) * 1000, 1)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate evaluation responses for MiniMe.")
    parser.add_argument("--mode", choices=["direct", "runtime"], default="direct",
                        help="direct: load model in-process; runtime: call running server (default: direct)")
    parser.add_argument("--adapter", default=str(ROOT / "output" / "captain-lora"),
                        help="Path to LoRA adapter dir (direct mode)")
    parser.add_argument("--base-only", action="store_true",
                        help="Load base Qwen model without LoRA adapter (baseline). direct mode only.")
    parser.add_argument("--label", default="finetuned",
                        help="Label for this model run, e.g. 'finetuned' or 'baseline'")
    parser.add_argument("--model-name", default="Qwen/Qwen3.5-9B",
                        help="Base model name (for baseline mode or labelling)")
    parser.add_argument("--server-url", default="http://127.0.0.1:8000",
                        help="Server URL for runtime mode")
    parser.add_argument("--prompts", default=str(PROMPTS_FILE),
                        help="Path to prompts JSONL file")
    parser.add_argument("--run-dir", default=None,
                        help="Output directory under reports/evaluation/. Defaults to YYYYMMDD-HHMMSS/")
    parser.add_argument("--dry-run", action="store_true",
                        help="Process only first 5 prompts (syntax/smoke test)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    prompts = load_prompts(Path(args.prompts))
    if args.dry_run:
        prompts = prompts[:5]
        print(f"[dry-run] Using {len(prompts)} prompts only")

    # Determine output dir
    run_dir_name = args.run_dir or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = REPORTS_BASE / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=True)

    responses_path = run_dir / f"responses_{args.label}.jsonl"
    print(f"Mode       : {args.mode}")
    print(f"Label      : {args.label}")
    print(f"Prompts    : {len(prompts)}")
    print(f"Output dir : {run_dir}")
    print(f"Output file: {responses_path}")
    print("=" * 60)

    results = []

    if args.mode == "runtime":
        # Check server health first
        import urllib.request as _ur
        try:
            with _ur.urlopen(f"{args.server_url}/health", timeout=5) as r:
                health = json.loads(r.read())
            if health.get("status") != "ready":
                print(f"[ERROR] Server not ready: {health.get('status')} — {health.get('error')}")
                sys.exit(1)
            print(f"Server OK  : {health.get('adapter_path')}")
        except Exception as e:
            print(f"[ERROR] Cannot reach server at {args.server_url}: {e}")
            sys.exit(1)

        for i, prompt in enumerate(prompts, 1):
            print(f"[{i:3d}/{len(prompts)}] {prompt['id']} ({prompt['category']})", end=" ... ", flush=True)
            result = run_runtime_generation(prompt, args.server_url)
            result["model_label"] = args.label
            result["model_name"] = args.label
            results.append(result)
            status = "OK" if result["ok"] else f"REJECTED ({result['guard_reason']})"
            print(f"{status} | {result['latency_ms']}ms | reply: {repr(result['final_reply'][:40])}")

    else:  # direct mode
        print("Loading model (direct mode)...")
        import torch

        if not torch.cuda.is_available():
            print("[ERROR] Direct mode requires CUDA GPU. Qwen 9B cannot run on CPU.")
            print("        Use --mode runtime (requires running server) or run on a GPU machine.")
            sys.exit(1)

        import unsloth  # noqa: F401
        from unsloth import FastLanguageModel

        if args.base_only:
            model_path = args.model_name
            print(f"Base model : {model_path} (no LoRA adapter)")
        else:
            model_path = args.adapter
            if not Path(model_path).exists():
                print(f"[ERROR] Adapter not found: {model_path}")
                sys.exit(1)
            print(f"Adapter    : {model_path}")

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_path,
            max_seq_length=MAX_SEQ_LEN,
            load_in_4bit=True,
            dtype=None,
        )
        FastLanguageModel.for_inference(model)
        chat_tokenizer = getattr(tokenizer, "tokenizer", tokenizer)
        chat_tokenizer.chat_template = SYSTEM_AWARE_CHAT_TEMPLATE

        print(f"Model loaded. GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
        print("=" * 60)

        for i, prompt in enumerate(prompts, 1):
            print(f"[{i:3d}/{len(prompts)}] {prompt['id']} ({prompt['category']})", end=" ... ", flush=True)
            result = run_direct_generation(model, chat_tokenizer, torch, prompt)
            result["model_label"] = args.label
            result["model_name"] = model_path if not args.base_only else args.model_name
            results.append(result)
            status = "OK" if result["ok"] else f"REJECTED ({result['guard_reason']})"
            print(f"{status} | {result['latency_ms']}ms | reply: {repr(result['final_reply'][:40])}")

    # Write output
    with responses_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    ok_count = sum(1 for r in results if r["ok"])
    rejected_count = len(results) - ok_count
    total_latency = sum(r["latency_ms"] for r in results)
    avg_latency = total_latency / len(results) if results else 0

    print("=" * 60)
    print(f"Done. {ok_count}/{len(results)} OK, {rejected_count} rejected")
    print(f"Avg latency: {avg_latency:.0f}ms")
    print(f"Saved: {responses_path}")
    print(f"Run dir: {run_dir}")
    print()
    print("Next steps:")
    print(f"  python evaluation/compute_metrics.py --run-dir {run_dir_name}")
    print(f"  python evaluation/prepare_human_eval.py --run-dir {run_dir_name}")


if __name__ == "__main__":
    main()
