# 🧠 MiniMe — ทำความเข้าใจโปรเจกต์

## ภาพรวม

**MiniMe** คือ pipeline สำหรับสร้าง dataset เพื่อ **Fine-tune LLM ให้พูดเหมือน "กัปปิตัน"** (เจ้าของโปรเจกต์) โดยนำข้อมูลการสนทนาจริงจาก **Instagram Direct Messages** มาประมวลผลผ่าน 7 ขั้นตอน จนได้ไฟล์ `train.jsonl` + `val.jsonl` แล้วนำไป Fine-tune ด้วย **Unsloth + LoRA** ผ่าน `training/train.py`

> [!NOTE]
> ข้อมูลเป็น **ภาษาไทย** ทั้งหมด และเน้นการสนทนา 1-on-1 เท่านั้น (ไม่รวม Group Chat)

---

## 📂 โครงสร้าง Folder

```
MiniMe/
├── data/
│   ├── raw_data/       ← วางข้อมูล Instagram DM export ที่นี่ (ไม่ถูก track ใน Git)
│   ├── filtered/       ← ผลลัพธ์หลัง clean & filter (step 04)
│   └── output/         ← ไฟล์ JSONL ขั้นสุดท้าย (step 05-07)
│       ├── base_data.jsonl
│       ├── tagged_data.jsonl
│       ├── train.jsonl
│       └── val.jsonl
│
├── scripts/            ← Python scripts ทั้ง 7 ขั้นตอน (data pipeline)
│   ├── 01_delete_media.py
│   ├── 02_rename_json.py
│   ├── 03_flatten_inbox.py
│   ├── 04_clean_and_filter.py
│   ├── 05_build_jsonl.py
│   ├── 06_tag_emotions.py
│   └── 07_split_train_val.py
│
├── training/           ← Fine-tuning scripts
│   └── train.py        ← Unsloth + LoRA fine-tuning script
│
├── output/             ← ผลลัพธ์จากการ train (ไม่ถูก track ใน Git)
│   └── captain-lora/   ← LoRA weights ที่ save หลัง train เสร็จ
│
├── captain-env/        ← Python Virtual Environment (ไม่ถูก track ใน Git)
├── unsloth_compiled_cache/  ← Auto-generated โดย Unsloth (ไม่ถูก track ใน Git)
├── requirements.txt
└── PROJECT_OVERVIEW.md
```

---

## 🔄 Pipeline ทั้ง 7 ขั้นตอน + Training

### Step 01 — `01_delete_media.py`
**ลบ folder สื่อออกจาก raw export**
- ค้นหา folder ชื่อ `audio`, `photos`, `videos` ใน `data/raw_data/`
- ลบทิ้งทั้งหมดด้วย `shutil.rmtree`
- ทำก่อนขั้นตอนอื่นทั้งหมด เพราะ Instagram export มี media files มาด้วยเสมอ

---

### Step 02 — `02_rename_json.py`
**ทำให้ชื่อไฟล์ JSON เป็นมาตรฐาน**
- Instagram export ตั้งชื่อ folder แบบ `username_randomhash/`
- Script จะ rename ไฟล์ JSON ข้างใน เช่น `message_1.json` → `username.json`
- ถ้ามีหลายไฟล์ จะ suffix เป็น `username_1.json`, `username_2.json`

---

### Step 03 — `03_flatten_inbox.py`
**ย้ายไฟล์ JSON ขึ้นมาที่ root ของ `data/raw_data/`**
- Instagram export เก็บ JSON ไว้ใน sub-folder ซ้อนกัน
- Script ย้ายไฟล์ขึ้น 1 ระดับ แล้วลบ sub-folder ทิ้ง
- ผลลัพธ์: ไฟล์ JSON ทุกไฟล์อยู่ที่ `data/raw_data/*.json` แบน ๆ

---

### Step 04 — `04_clean_and_filter.py`
**ทำความสะอาดข้อความ + กรองการสนทนา**

| ฟีเจอร์ | รายละเอียด |
|---|---|
| แก้ encoding | Thai text ที่ถูก save ผิดเป็น Latin1 → แปลงกลับเป็น UTF-8 |
| ลบข้อความระบบ | "sent an attachment", "แชร์โพสต์", "started an audio call" ฯลฯ |
| ลบ URL | https, www, facebook.com, instagram.com, youtube.com |
| กรอง Group Chat | ถ้ามี participants > 2 คน → ข้ามทั้ง conversation |
| กรอง Monologue | ถ้ามีแค่คนเดียวพูด → ข้ามทั้ง conversation |

- **Output:** `data/filtered/*.json` (รูปแบบ: list ของ `{sender, content, timestamp}`)

---

### Step 05 — `05_build_jsonl.py`
**แปลงเป็น OpenAI-style JSONL format**

**Logic สำคัญ:**
- `ASSISTANT_NAME = "กัปปิตัน"` — ข้อความของกัปปิตัน = `role: assistant`, คนอื่น = `role: user`
- แบ่ง session โดยใช้ **time gap > 1 ชั่วโมง** = session ใหม่
- Merge ข้อความติดกันจาก role เดียวกัน (เช่น ส่ง 3 ข้อความรัวๆ → รวมเป็น 1 turn)
- ตัด leading assistant turns ออก (session ต้องเริ่มด้วย user)
- กรอง session ที่ไม่มีทั้ง user และ assistant

- **Output:** `data/output/base_data.jsonl`

**รูปแบบ output:**
```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

---

### Step 06 — `06_tag_emotions.py`
**ตรวจจับอารมณ์จากอีโมจิและคำ แล้วแท็กท้ายข้อความ**

**Emotion Tags ที่รองรับ (12 tags):**
| Tag | อารมณ์ | ตัวอย่างอีโมจิ |
|---|---|---|
| `[เศร้า]` | เศร้า/ผิดหวัง | 😭😢😔🥺🥹 |
| `[ขำ]` | ขำ/ตลก | 😂🤣💀😆 + "555" |
| `[โกรธ]` | โกรธ/หงุดหงิด | 😡🤬😤😠 |
| `[ดีใจ]` | ดีใจ/ตื่นเต้น | 🥳🎉🎊👏🔥 |
| `[อบอุ่น]` | รัก/อบอุ่น | 😘💖💕🥰❤ |
| `[ขอร้อง]` | ขอร้อง/ภาวนา | 🙏 |
| `[มีความสุข]` | ยิ้ม/มีความสุข | 😄🙂😁😀🤩 |
| `[ตกใจ]` | ตกใจ/ประหลาดใจ | 😱😮🫣 |
| `[สงสัย]` | สงสัย/คิด | 🤔🧐🤨 |
| `[เบื่อ]` | เบื่อ/เฉยชา | 😑 |
| `[ให้กำลังใจ]` | ให้กำลังใจ | ✌ |
| `[มั่นใจ]` | มั่นใจ/เท่ | 😎 |

**Logic:**
1. สแกนทุก character ในข้อความ → เช็คว่าอยู่ใน `emotion_map` ไหม
2. นับ "555" ด้วย (= `[ขำ]`)
3. ถ้ามีหลาย emotion → เลือก **อันที่เจอบ่อยที่สุด** (most common)
4. append tag ท้ายข้อความ: `"เนื้อหา [เศร้า]"`
5. ลบ system messages ออก

- **Input:** `data/output/base_data.jsonl`
- **Output:** `data/output/tagged_data.jsonl`

---

### Step 07 — `07_split_train_val.py`
**แบ่ง dataset เป็น Train / Validation**
- สุ่ม shuffle ด้วย `random.seed(42)` (reproducible)
- แบ่ง **95% train / 5% validation**
- **Output:** `data/output/train.jsonl` + `data/output/val.jsonl`

---

### Step 08 — `training/train.py` ⭐ (Fine-tuning)
**Fine-tune LLM ด้วย Unsloth + LoRA บน dataset ที่เตรียมไว้**

**Model & Config:**
| Parameter | Value |
|---|---|
| Base Model | `scb10x/typhoon2-qwen2.5-7b-instruct` |
| Max Sequence Length | `2048` |
| Quantization | 4-bit (`load_in_4bit=True`) |
| LoRA Rank (r) | `16` |
| LoRA Alpha | `32` |
| LoRA Dropout | `0.05` |
| Target Modules | `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj` |
| Gradient Checkpointing | `"unsloth"` |

**Training Hyperparameters:**
| Parameter | Value |
|---|---|
| Learning Rate | `2e-4` |
| LR Scheduler | `cosine` |
| Batch Size (per device) | `2` |
| Gradient Accumulation Steps | `4` (effective batch = 8) |
| Epochs | `3` |
| Precision | `bf16` (ถ้ารองรับ) / `fp16` (fallback) |
| Optimizer | `adamw_8bit` |
| Warmup Ratio | `0.05` |
| Weight Decay | `0.01` |
| Eval Steps | ทุก `200` steps |
| Save Steps | ทุก `500` steps |
| Save Total Limit | `2` checkpoints |
| Dataset num_proc | `1` (Windows compatibility) |

**Pipeline 5 ขั้นตอนใน train.py:**
1. **Load base model** — โหลด Typhoon2 ด้วย Unsloth
2. **Apply LoRA** — ใส่ LoRA adapters เข้าไปใน attention + FFN layers
3. **Load dataset** — โหลด `train.jsonl` + `val.jsonl` แล้ว format ด้วย chat template
4. **Setup SFTTrainer** — ตั้งค่า trainer พร้อม TrainingArguments
5. **Train & Save** — train แล้ว save LoRA weights ลง `output/captain-lora/`

**การ Format Dataset:**
```python
# ใช้ tokenizer.apply_chat_template() โดยไม่ใส่ system prompt
text = tokenizer.apply_chat_template(
    example["messages"],
    tokenize=False,
    add_generation_prompt=False
)
```

**ระยะเวลาโดยประมาณ:** ~3-6 ชั่วโมง (ขึ้นอยู่กับ GPU)

- **Input:** `data/output/train.jsonl` + `data/output/val.jsonl`
- **Output:** `output/captain-lora/` (LoRA adapter weights + tokenizer)

---

## 🔁 Data Flow สรุป (ครบทั้งหมด)

```
Instagram DM Export (raw JSON)
        │
        ▼ 01_delete_media.py
   ลบ audio/photos/videos folders
        │
        ▼ 02_rename_json.py
   ตั้งชื่อไฟล์ใหม่ (username.json)
        │
        ▼ 03_flatten_inbox.py
   ย้ายไฟล์ขึ้นมาที่ root
        │
        ▼ 04_clean_and_filter.py
   clean encoding + ลบ noise + กรอง 1-on-1
        │ → data/filtered/*.json
        ▼ 05_build_jsonl.py
   แปลงเป็น OpenAI chat format + แบ่ง session
        │ → data/output/base_data.jsonl
        ▼ 06_tag_emotions.py
   ตรวจจับอารมณ์ + แท็กข้อความ
        │ → data/output/tagged_data.jsonl
        ▼ 07_split_train_val.py
   95% train / 5% validation split
        │
        ├── data/output/train.jsonl  ✅
        └── data/output/val.jsonl   ✅
                │
                ▼ training/train.py
   Unsloth + LoRA Fine-tuning (Typhoon2-7B)
        │
        └── output/captain-lora/    🎯 (LoRA weights พร้อมใช้งาน)
```

---

## 📊 Dataset Statistics (ข้อมูลจริง)

> [!NOTE]
> สถิติจากการรัน `python -X utf8 scripts/count_stats.py`

### ก่อน Clean — `raw_data/`

| รายการ | จำนวน |
|---|---:|
| Conversations (folders) | **161** |
| Group chats (ถูก skip) | 10 |
| ข้อความที่มี content | **48,254** |

### หลัง Clean — `filtered/`

| รายการ | จำนวน |
|---|---:|
| Conversations ที่เหลือ | **129** |
| Conversations ที่ถูกตัดออก | 32 |
| ข้อความที่เหลือ | **34,064** |
| ข้อความที่ถูกตัดออก | 14,190 |
| Retention rate | **70.6%** |

### Sessions — `base_data.jsonl`

| รายการ | จำนวน |
|---|---:|
| Total sessions | **3,065** |
| Total turns (messages) | 17,950 |
| Avg turns per session | **5.9** |

### Train / Val Split

| ไฟล์ | Sessions | Messages | Avg turns | สัดส่วน |
|---|---:|---:|---:|---:|
| `train.jsonl` | **2,911** | **17,062** | 5.9 | 95% |
| `val.jsonl` | **154** | **888** | 5.8 | 5% |

---

## ⚙️ Key Dependencies

| Library | ใช้ทำอะไร |
|---|---|
| `unsloth` | เร่งความเร็วการ fine-tune LLM |
| `transformers` | Hugging Face model loading |
| `torch` | PyTorch framework |
| `accelerate` | Distributed training support |
| `bitsandbytes` | Quantization (4-bit/8-bit) |
| `datasets` | Data loading สำหรับ training |
| `trl` | SFTTrainer สำหรับ Supervised Fine-Tuning |

---

## 📋 Quick Start

```bash
# 1. Activate virtual environment
captain-env\Scripts\activate

# ── Data Pipeline (ทำครั้งเดียวต่อ dataset ใหม่) ──
python scripts/01_delete_media.py
python scripts/02_rename_json.py
python scripts/03_flatten_inbox.py

# ── Processing (รันซ้ำได้เสมอ) ──
python scripts/04_clean_and_filter.py
python scripts/05_build_jsonl.py
python scripts/06_tag_emotions.py
python scripts/07_split_train_val.py

# ── Fine-tuning (~3-6 ชั่วโมง) ──
python training/train.py

# ── ผลลัพธ์ ──
# output/captain-lora/   ← LoRA weights พร้อมใช้งาน
```

---

## 📌 สิ่งที่ควรรู้เพิ่มเติม

> [!IMPORTANT]
> ไฟล์ใน `data/`, `captain-env/`, `unsloth_compiled_cache/`, และ `output/` ถูกระบุใน `.gitignore` ทั้งหมด — จะไม่ถูก commit ขึ้น Git

> [!TIP]
> ขั้นตอนที่ 1-3 รัน **ครั้งเดียว** ต่อ dataset ใหม่ (ทำลาย raw data structure) ส่วนขั้นตอน 4-7 รันซ้ำได้เสมอ

> [!TIP]
> `training/train.py` ใช้ `dataset_num_proc=1` เพื่อหลีกเลี่ยงปัญหา multiprocessing บน Windows

> [!NOTE]
> Base model ที่ใช้คือ **Typhoon2-Qwen2.5-7B-Instruct** (`scb10x/typhoon2-qwen2.5-7b-instruct`) ซึ่งเป็นโมเดลภาษาไทยที่ถูก fine-tune มาแล้ว เหมาะสำหรับการ fine-tune ต่อด้วยข้อมูลภาษาไทย
