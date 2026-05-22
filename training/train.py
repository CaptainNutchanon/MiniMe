import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import unsloth
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
from pathlib import Path
import torch

# ── Config ──────────────────────────────────────────
ROOT         = Path(__file__).parent.parent  # d:/GitHub/MiniMe/
MODEL_NAME   = "scb10x/typhoon2-qwen2.5-7b-instruct"
TRAIN_FILE   = str(ROOT / "data" / "output" / "train.jsonl")
VAL_FILE     = str(ROOT / "data" / "output" / "val.jsonl")
OUTPUT_DIR   = str(ROOT / "output" / "captain-lora")
MAX_SEQ_LEN  = 2048
LOAD_IN_4BIT = True
# ─────────────────────────────────────────────────────

print("=" * 50)
print("MiniMe - Captain Fine-tuning")
print("=" * 50)
print(f"Model : {MODEL_NAME}")
print(f"CUDA  : {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU   : {torch.cuda.get_device_name(0)}")
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"VRAM  : {vram:.1f} GB")
print("=" * 50)

# 1. Load model
print("\n[1/5] Loading base model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name     = MODEL_NAME,
    max_seq_length = MAX_SEQ_LEN,
    load_in_4bit   = LOAD_IN_4BIT,
    dtype          = None,
)
print("      Base model loaded!")

# 2. LoRA
print("\n[2/5] Applying LoRA...")
model = FastLanguageModel.get_peft_model(
    model,
    r              = 16,
    target_modules = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_alpha     = 32,
    lora_dropout   = 0.05,
    bias           = "none",
    use_gradient_checkpointing = "unsloth",
    random_state   = 42,
)
print("      LoRA applied!")

# 3. Load dataset
print("\n[3/5] Loading dataset...")
dataset = load_dataset(
    "json",
    data_files={
        "train"     : TRAIN_FILE,
        "validation": VAL_FILE
    }
)
print(f"      Train : {len(dataset['train'])} sessions")
print(f"      Val   : {len(dataset['validation'])} sessions")

# Format โดยไม่ใส่ system prompt
def format_chat(example):
    text = tokenizer.apply_chat_template(
        example["messages"],
        tokenize=False,
        add_generation_prompt=False
    )
    return {"text": text}

dataset = dataset.map(format_chat, desc="Formatting")
print("      Dataset formatted!")

# 4. Trainer
print("\n[4/5] Setting up trainer...")
trainer = SFTTrainer(
    model              = model,
    tokenizer          = tokenizer,
    train_dataset      = dataset["train"],
    eval_dataset       = dataset["validation"],
    dataset_text_field = "text",
    max_seq_length     = MAX_SEQ_LEN,
    dataset_num_proc   = 1,   # Windows: multiprocessing > 1 อาจมีปัญหา
    args = TrainingArguments(
        learning_rate               = 2e-4,
        lr_scheduler_type           = "cosine",
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        num_train_epochs            = 3,
        bf16                        = torch.cuda.is_bf16_supported(),
        fp16                        = not torch.cuda.is_bf16_supported(),
        logging_steps               = 50,
        eval_strategy               = "steps",
        eval_steps                  = 200,
        save_steps                  = 500,
        save_total_limit            = 2,
        output_dir                  = OUTPUT_DIR,
        optim                       = "adamw_8bit",
        warmup_ratio                = 0.05,
        weight_decay                = 0.01,
        report_to                   = "none",
    ),
)
print("      Trainer ready!")

# 5. Train
print("\n[5/5] Starting training...")
print("      (ใช้เวลาประมาณ 3-6 ชั่วโมง)\n")
trainer_stats = trainer.train()

# 6. Save
print("\nSaving LoRA weights...")
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

print("\n" + "=" * 50)
print("Training Complete!")
print(f"Time   : {trainer_stats.metrics['train_runtime']/3600:.2f} hours")
print(f"Saved  : {OUTPUT_DIR}")
print("=" * 50)