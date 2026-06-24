import multiprocessing as mp
import argparse
import csv
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Config
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from minime_core.runtime_env import configure_utf8
from minime_core.text_cleaning import clean_content, is_usable_content
from minime_core.topic_guard import training_skip_reason

configure_utf8()

TRAIN_FILE = str(ROOT / "data" / "output" / "train.jsonl")
VAL_FILE = str(ROOT / "data" / "output" / "val.jsonl")
CURATED_TRAIN_FILE = str(ROOT / "data" / "curated" / "general_chat_train.jsonl")
CURATED_VAL_FILE = str(ROOT / "data" / "curated" / "general_chat_val.jsonl")
DEFAULT_MODEL_NAME = "Qwen/Qwen3.5-9B"
DEFAULT_OUTPUT_DIR = ROOT / "output" / "candidates" / "captain-lora-20260610-minfilter"
TRAINING_REPORT_DIR = ROOT / "reports" / "training"
PROTECTED_OUTPUT_DIRS = {
    (ROOT / "output" / "captain-lora").resolve(),
    (ROOT / "output" / "captain-lora-candidate").resolve(),
}
OVERWRITABLE_OUTPUT_DIRS = {DEFAULT_OUTPUT_DIR.resolve()}
OVERWRITE_OUTPUT_ENV = "MINIME_OVERWRITE_OUTPUT"
MODEL_NAME = os.environ.get("MINIME_BASE_MODEL", DEFAULT_MODEL_NAME)
OUTPUT_DIR_PATH = Path(os.environ.get("MINIME_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
if not OUTPUT_DIR_PATH.is_absolute():
    OUTPUT_DIR_PATH = ROOT / OUTPUT_DIR_PATH
OUTPUT_DIR_PATH = OUTPUT_DIR_PATH.resolve()
if OUTPUT_DIR_PATH in PROTECTED_OUTPUT_DIRS:
    protected = ", ".join(str(path) for path in sorted(PROTECTED_OUTPUT_DIRS))
    raise ValueError(f"Refusing to write training output to protected adapter dir: {OUTPUT_DIR_PATH}. Protected: {protected}")
OUTPUT_DIR = str(OUTPUT_DIR_PATH)
MAX_SEQ_LEN = 2048
LOAD_IN_4BIT = True
MAX_CONTEXT_TURNS = 8
MAX_COMPLETION_CHARS = 60
CURATED_REPEAT = 2
TRAIN_EPOCHS = 2
EVAL_STEPS = 100
SAVE_STEPS = 100
SAVE_TOTAL_LIMIT = 10
CHAT_TEMPLATE = """{%- for message in messages %}
    {%- if message['role'] == 'system' %}
{{- '<|im_start|>system\n' + message['content'] + '<|im_end|>\n' }}
    {%- elif message['role'] == 'user' %}
{{- '<|im_start|>user\n' + message['content'] + '<|im_end|>\n' }}
    {%- elif message['role'] == 'assistant' %}
{{- '<|im_start|>assistant\n' }}
{% generation %}{{- message['content'] }}{% endgeneration %}
{{- '<|im_end|>\n' }}
    {%- endif %}
{%- endfor %}
{%- if add_generation_prompt %}
{{- '<|im_start|>assistant\n' }}
{%- endif %}"""


def write_training_report(trainer, trainer_stats, data_summary: dict) -> dict[str, str]:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    TRAINING_REPORT_DIR.mkdir(parents=True, exist_ok=True)

    log_history = [dict(entry) for entry in trainer.state.log_history]
    final_metrics = dict(trainer_stats.metrics)
    best_metric = getattr(trainer.state, "best_metric", None)
    best_checkpoint = getattr(trainer.state, "best_model_checkpoint", None)
    report = {
        "timestamp": timestamp,
        "model": MODEL_NAME,
        "output_dir": OUTPUT_DIR,
        "config": {
            "max_seq_len": MAX_SEQ_LEN,
            "max_context_turns": MAX_CONTEXT_TURNS,
            "max_completion_chars": MAX_COMPLETION_CHARS,
            "curated_repeat": CURATED_REPEAT,
            "num_train_epochs": TRAIN_EPOCHS,
            "eval_steps": EVAL_STEPS,
            "save_steps": SAVE_STEPS,
            "save_total_limit": SAVE_TOTAL_LIMIT,
            "load_best_model_at_end": True,
            "metric_for_best_model": "eval_loss",
            "greater_is_better": False,
            "label_mode": "last_assistant_only",
        },
        "data": data_summary,
        "best_metric": best_metric,
        "best_model_checkpoint": best_checkpoint,
        "final_metrics": final_metrics,
        "log_history": log_history,
    }

    json_path = TRAINING_REPORT_DIR / f"training_metrics_{timestamp}.json"
    csv_path = TRAINING_REPORT_DIR / f"training_metrics_{timestamp}.csv"
    md_path = TRAINING_REPORT_DIR / f"training_summary_{timestamp}.md"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    metric_rows = [
        entry
        for entry in log_history
        if any(key in entry for key in ("loss", "eval_loss", "train_loss"))
    ]
    fieldnames = [
        "step",
        "epoch",
        "loss",
        "eval_loss",
        "train_loss",
        "learning_rate",
        "grad_norm",
        "train_runtime",
        "train_samples_per_second",
        "train_steps_per_second",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in metric_rows:
            writer.writerow(row)

    lines = [
        "# MiniMe Training Metrics",
        "",
        f"- Timestamp: {timestamp}",
        f"- Model: `{MODEL_NAME}`",
        f"- Output dir: `{OUTPUT_DIR}`",
        f"- Best checkpoint: `{best_checkpoint}`",
        f"- Best eval_loss: `{best_metric}`",
        f"- Final train_loss: `{final_metrics.get('train_loss')}`",
        f"- Train runtime hours: `{final_metrics.get('train_runtime', 0) / 3600:.4f}`",
        "",
        "## Config",
        "",
        "| key | value |",
        "| --- | --- |",
    ]
    for key, value in report["config"].items():
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Data",
            "",
            "| key | value |",
            "| --- | --- |",
        ]
    )
    for key, value in data_summary.items():
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Loss Log",
            "",
            "| step | epoch | train loss | eval loss | learning rate |",
            "| ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in metric_rows:
        lines.append(
            "| {step} | {epoch} | {loss} | {eval_loss} | {learning_rate} |".format(
                step=row.get("step", ""),
                epoch=row.get("epoch", ""),
                loss=row.get("loss", row.get("train_loss", "")),
                eval_loss=row.get("eval_loss", ""),
                learning_rate=row.get("learning_rate", ""),
            )
        )

    with md_path.open("w", encoding="utf-8-sig") as file:
        file.write("\n".join(lines) + "\n")

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(md_path),
    }


def prepare_output_dir() -> None:
    if not OUTPUT_DIR_PATH.exists():
        return
    if os.environ.get(OVERWRITE_OUTPUT_ENV) != "1":
        if OUTPUT_DIR_PATH in OVERWRITABLE_OUTPUT_DIRS:
            raise ValueError(
                f"Output dir already exists: {OUTPUT_DIR_PATH}. "
                f"Set {OVERWRITE_OUTPUT_ENV}=1 to overwrite this candidate."
            )
        return
    if OUTPUT_DIR_PATH not in OVERWRITABLE_OUTPUT_DIRS:
        raise ValueError(f"Refusing to overwrite non-candidate output dir: {OUTPUT_DIR_PATH}")
    if OUTPUT_DIR_PATH in PROTECTED_OUTPUT_DIRS:
        raise ValueError(f"Refusing to overwrite protected adapter dir: {OUTPUT_DIR_PATH}")
    print(f"Overwriting existing output dir: {OUTPUT_DIR_PATH}")
    shutil.rmtree(OUTPUT_DIR_PATH)


def build_turn_examples(split):
    examples = []
    stats = {
        "sessions": 0,
        "skipped_empty_or_noisy": 0,
        "skipped_long": 0,
        "skipped_no_user_context": 0,
        "skipped_personal_number": 0,
        "skipped_other": 0,
        "kept": 0,
    }
    for session in split:
        stats["sessions"] += 1
        source = str(session.get("source") or "unknown")
        cleaned_messages = []
        for message in session["messages"]:
            content = clean_content(message["content"])
            if not is_usable_content(content):
                stats["skipped_empty_or_noisy"] += 1
                continue
            cleaned_messages.append({"role": message["role"], "content": content})

        for index, message in enumerate(cleaned_messages):
            if message["role"] != "assistant":
                continue
            completion = message["content"]
            if len(completion) > MAX_COMPLETION_CHARS:
                stats["skipped_long"] += 1
                continue

            context = cleaned_messages[max(0, index - MAX_CONTEXT_TURNS) : index]
            skip_reason = training_skip_reason(completion, context)
            if skip_reason:
                if skip_reason == "no_user_context":
                    stats["skipped_no_user_context"] += 1
                elif skip_reason == "personal_number":
                    stats["skipped_personal_number"] += 1
                else:
                    stats["skipped_other"] += 1
                continue

            context_messages = [
                {"role": context_message["role"], "content": context_message["content"]}
                for context_message in context
            ]
            assistant_message = {"role": "assistant", "content": message["content"]}
            examples.append({"source": source, "messages": [*context_messages, assistant_message]})
            stats["kept"] += 1
    return examples, stats


def load_curated_examples(path, repeat=1):
    path = Path(path)
    examples = []
    stats = {
        "file": str(path),
        "exists": path.exists(),
        "loaded": 0,
        "repeated": 0,
        "skipped": 0,
    }
    if not path.exists():
        return examples, stats

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                session = json.loads(line)
            except json.JSONDecodeError:
                stats["skipped"] += 1
                continue

            messages = session.get("messages", [])
            if not isinstance(messages, list) or len(messages) < 2:
                stats["skipped"] += 1
                continue
            if messages[-1].get("role") != "assistant":
                stats["skipped"] += 1
                continue

            cleaned_messages = []
            for message in messages:
                role = message.get("role")
                content = clean_content(str(message.get("content", "")))
                if role not in {"user", "assistant"} or not is_usable_content(content):
                    continue
                cleaned_messages.append({"role": role, "content": content})

            if len(cleaned_messages) < 2 or cleaned_messages[-1]["role"] != "assistant":
                stats["skipped"] += 1
                continue
            examples.append({"source": path.name, "messages": cleaned_messages})
            stats["loaded"] += 1

    repeated_examples = examples * repeat
    stats["repeated"] = len(repeated_examples)
    return repeated_examples, stats


def prepare_training_rows(train_split, val_split) -> tuple[list[dict], list[dict], dict, dict]:
    train_examples, train_stats = build_turn_examples(train_split)
    val_examples, val_stats = build_turn_examples(val_split)
    curated_train_examples, curated_train_stats = load_curated_examples(CURATED_TRAIN_FILE, repeat=CURATED_REPEAT)
    curated_val_examples, curated_val_stats = load_curated_examples(CURATED_VAL_FILE, repeat=1)

    train_rows = train_examples + curated_train_examples
    val_rows = val_examples + curated_val_examples
    data_summary = {
        "train_sessions": len(train_split),
        "validation_sessions": len(val_split),
        "raw_train_examples": len(train_examples),
        "raw_validation_examples": len(val_examples),
        "raw_train_skipped_long": train_stats["skipped_long"],
        "raw_validation_skipped_long": val_stats["skipped_long"],
        "raw_train_skipped_no_user_context": train_stats["skipped_no_user_context"],
        "raw_validation_skipped_no_user_context": val_stats["skipped_no_user_context"],
        "raw_train_skipped_personal_number": train_stats["skipped_personal_number"],
        "raw_validation_skipped_personal_number": val_stats["skipped_personal_number"],
        "curated_train_examples": len(curated_train_examples),
        "curated_validation_examples": len(curated_val_examples),
        "final_train_examples": len(train_rows),
        "final_validation_examples": len(val_rows),
    }
    diagnostics = {
        "train_stats": train_stats,
        "val_stats": val_stats,
        "curated_train_stats": curated_train_stats,
        "curated_val_stats": curated_val_stats,
    }
    return train_rows, val_rows, data_summary, diagnostics


def print_data_diagnostics(train_rows: list[dict], val_rows: list[dict], diagnostics: dict) -> None:
    print(f"      Train examples : {len(train_rows)} assistant turns")
    print(f"      Val examples   : {len(val_rows)} assistant turns")
    print(f"      Train stats    : {diagnostics['train_stats']}")
    print(f"      Val stats      : {diagnostics['val_stats']}")
    print(f"      Curated train  : {diagnostics['curated_train_stats']}")
    print(f"      Curated val    : {diagnostics['curated_val_stats']}")


def load_jsonl_sessions(path: str) -> list[dict]:
    sessions = []
    with Path(path).open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            sessions.append(json.loads(line))
    return sessions


def run_data_check_only() -> None:
    print("=" * 50)
    print("MiniMe - Training Data Check Only")
    print("=" * 50)
    print(f"MAX_CONTEXT_TURNS = {MAX_CONTEXT_TURNS}")
    print(f"MAX_COMPLETION_CHARS = {MAX_COMPLETION_CHARS}")
    print(f"CURATED_REPEAT = {CURATED_REPEAT}")
    print("label_mode = last_assistant_only")
    print("=" * 50)

    train_split = load_jsonl_sessions(TRAIN_FILE)
    val_split = load_jsonl_sessions(VAL_FILE)
    print(f"      Train sessions : {len(train_split)}")
    print(f"      Val sessions   : {len(val_split)}")

    train_rows, val_rows, data_summary, diagnostics = prepare_training_rows(train_split, val_split)
    print_data_diagnostics(train_rows, val_rows, diagnostics)
    print("      Data summary   :")
    for key, value in data_summary.items():
        print(f"        {key}: {value}")
    print("=" * 50)
    print("Data check complete. No model loaded and no training started.")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Fine-tune or inspect MiniMe training data.")
    parser.add_argument("--data-check-only", action="store_true", help="Build/filter train rows and print counts without loading the model.")
    args = parser.parse_args()
    if args.data_check_only:
        run_data_check_only()
        return

    import unsloth
    import torch
    from datasets import Dataset, DatasetDict, load_dataset
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel

    print("=" * 50)
    print("MiniMe - Captain Fine-tuning")
    print("=" * 50)
    print(f"Model : {MODEL_NAME}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"MAX_CONTEXT_TURNS = {MAX_CONTEXT_TURNS}")
    print(f"MAX_COMPLETION_CHARS = {MAX_COMPLETION_CHARS}")
    print(f"CURATED_REPEAT = {CURATED_REPEAT}")
    print(f"num_train_epochs = {TRAIN_EPOCHS}")
    print(f"eval_steps = {EVAL_STEPS}")
    print(f"save_steps = {SAVE_STEPS}")
    print(f"save_total_limit = {SAVE_TOTAL_LIMIT}")
    print("label_mode = last_assistant_only")
    print("load_best_model_at_end = True")
    print("metric_for_best_model = eval_loss")
    print(f"CUDA  : {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU   : {torch.cuda.get_device_name(0)}")
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"VRAM  : {vram:.1f} GB")
    print("=" * 50)
    prepare_output_dir()

    # 1. Load model
    print("\n[1/5] Loading base model...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LEN,
        load_in_4bit=LOAD_IN_4BIT,
        dtype=None,
    )
    template_tokenizer = getattr(tokenizer, "tokenizer", tokenizer)
    template_tokenizer.chat_template = CHAT_TEMPLATE
    print("      Base model loaded!")

    # 2. LoRA
    print("\n[2/5] Applying LoRA...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )
    print("      LoRA applied!")

    # 3. Load dataset
    print("\n[3/5] Loading dataset...")
    dataset = load_dataset(
        "json",
        data_files={
            "train": TRAIN_FILE,
            "validation": VAL_FILE,
        },
    )
    print(f"      Train : {len(dataset['train'])} sessions")
    print(f"      Val   : {len(dataset['validation'])} sessions")

    train_rows, val_rows, data_summary, diagnostics = prepare_training_rows(
        dataset["train"],
        dataset["validation"],
    )
    dataset = DatasetDict({
        "train": Dataset.from_list(train_rows),
        "validation": Dataset.from_list(val_rows),
    })
    print_data_diagnostics(train_rows, val_rows, diagnostics)

    def build_last_assistant_labels(input_ids, assistant_mask, end_token_ids):
        labels = [-100] * len(input_ids)
        last_assistant_index = None
        for index, is_assistant_token in enumerate(assistant_mask):
            if is_assistant_token:
                last_assistant_index = index

        if last_assistant_index is None:
            return labels

        first_assistant_index = last_assistant_index
        while first_assistant_index > 0 and assistant_mask[first_assistant_index - 1]:
            first_assistant_index -= 1

        for index in range(first_assistant_index, last_assistant_index + 1):
            labels[index] = input_ids[index]

        end_index = last_assistant_index + 1
        if end_index < len(input_ids) and input_ids[end_index] in end_token_ids:
            labels[end_index] = input_ids[end_index]

        return labels

    def tokenize_chat(example):
        processed = template_tokenizer.apply_chat_template(
            example["messages"],
            tokenize=True,
            add_generation_prompt=False,
            return_dict=True,
            return_assistant_tokens_mask=True,
            truncation=True,
            max_length=MAX_SEQ_LEN,
        )
        input_ids = processed["input_ids"]
        attention_mask = processed["attention_mask"]
        assistant_mask = processed["assistant_masks"]
        im_end_token_id = template_tokenizer.convert_tokens_to_ids("<|im_end|>")
        end_token_ids = {
            token_id
            for token_id in (template_tokenizer.eos_token_id, im_end_token_id)
            if isinstance(token_id, int)
        }
        labels = build_last_assistant_labels(input_ids, assistant_mask, end_token_ids)
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }

    dataset = dataset.map(
        tokenize_chat,
        desc="Tokenizing with last-assistant-only labels",
        num_proc=None,
        remove_columns=dataset["train"].column_names,
    )
    print("      Dataset tokenized with last-assistant-only labels!")

    class AssistantOnlyDataCollator:
        def __init__(self, pad_token_id: int, label_pad_token_id: int = -100) -> None:
            self.pad_token_id = pad_token_id
            self.label_pad_token_id = label_pad_token_id

        def __call__(self, features):
            max_length = max(len(feature["input_ids"]) for feature in features)
            batch = {"input_ids": [], "attention_mask": [], "labels": []}
            for feature in features:
                length = len(feature["input_ids"])
                pad_length = max_length - length
                batch["input_ids"].append(feature["input_ids"] + [self.pad_token_id] * pad_length)
                batch["attention_mask"].append(feature["attention_mask"] + [0] * pad_length)
                batch["labels"].append(feature["labels"] + [self.label_pad_token_id] * pad_length)
            return {key: torch.tensor(value, dtype=torch.long) for key, value in batch.items()}

    pad_token_id = template_tokenizer.pad_token_id
    if pad_token_id is None:
        pad_token_id = template_tokenizer.eos_token_id
    data_collator = AssistantOnlyDataCollator(pad_token_id)

    # 4. Trainer
    print("\n[4/5] Setting up trainer...")
    trainer = SFTTrainer(
        model=model,
        processing_class=template_tokenizer,
        data_collator=data_collator,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        args=SFTConfig(
            dataset_num_proc=None,  # Windows: disable datasets multiprocessing.
            max_length=MAX_SEQ_LEN,
            packing=False,
            learning_rate=2e-4,
            lr_scheduler_type="cosine",
            per_device_train_batch_size=1,
            gradient_accumulation_steps=8,
            num_train_epochs=TRAIN_EPOCHS,
            bf16=torch.cuda.is_bf16_supported(),
            fp16=not torch.cuda.is_bf16_supported(),
            logging_steps=50,
            eval_strategy="steps",
            eval_steps=EVAL_STEPS,
            save_steps=SAVE_STEPS,
            save_total_limit=SAVE_TOTAL_LIMIT,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            output_dir=OUTPUT_DIR,
            optim="adamw_8bit",
            warmup_ratio=0.05,
            weight_decay=0.01,
            report_to="none",
            remove_unused_columns=False,
        ),
    )
    print("      Trainer ready!")

    # 5. Train
    print("\n[5/5] Starting training...")
    print("      (Estimated training time: 1-2 hours depending on GPU)\n")
    trainer_stats = trainer.train()

    # 6. Save
    print("\nSaving LoRA weights...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    report_paths = write_training_report(trainer, trainer_stats, data_summary)

    print("\n" + "=" * 50)
    print("Training Complete!")
    print(f"Time   : {trainer_stats.metrics['train_runtime'] / 3600:.2f} hours")
    print(f"Saved  : {OUTPUT_DIR}")
    print(f"Report : {report_paths['markdown']}")
    print(f"Metrics: {report_paths['json']}")
    print(f"CSV    : {report_paths['csv']}")
    print("=" * 50)


if __name__ == "__main__":
    mp.freeze_support()
    main()
