# MiniMe Project Overview & Technical Specification

> **สถานะเอกสาร:** Single Source of Truth สำหรับสถาปัตยกรรม ข้อมูล การฝึก รันไทม์ และการประเมินผลของ MiniMe
>
> **ตรวจสอบกับโค้ดล่าสุด:** 24 มิถุนายน 2026
>
> **ขอบเขต:** เอกสารนี้อธิบายสิ่งที่ repository ทำอยู่จริง ไม่ใช่ข้อเสนอสำหรับระบบในอนาคต

## สารบัญ

1. [ภาพรวมโปรเจกต์](#1-ภาพรวมโปรเจกต์-project-overview)
2. [โครงสร้างและการจัดระเบียบข้อมูล](#2-โครงสร้างและการจัดระเบียบข้อมูล-detailed-project-directory)
3. [Dataset Pipeline และ Preprocessing](#3-สถาปัตยกรรมข้อมูลแชทและการทำความสะอาด-dataset-pipeline--preprocessing)
4. [Training และ LoRA Fine-tuning](#4-กระบวนการฝึกฝนแบบจำลอง-training--lora-fine-tuning)
5. [Runtime และ Safety Guard](#5-สถาปัตยกรรมรันไทม์และระบบป้องกัน-runtime--safety-guard)
6. [Frontend และ Local Storage](#6-เว็บอินเทอร์เฟซและการจัดเก็บประวัติ-frontend--local-storage)
7. [Evaluation Framework](#7-กรอบการประเมินผลและการทดสอบ-evaluation-framework)
8. [คู่มือใช้งานสำหรับนักพัฒนา](#8-คู่มือใช้งานสำหรับนักพัฒนา)
9. [ข้อจำกัดและความเสี่ยง](#9-ข้อจำกัดและความเสี่ยงของระบบปัจจุบัน)
10. [กติกาการดูแลเอกสาร](#10-กติกาการดูแล-single-source-of-truth)

---

## 1. ภาพรวมโปรเจกต์ (Project Overview)

### 1.1 MiniMe คืออะไร

MiniMe คือเว็บแชทภาษาไทยที่ทำงานบนเครื่องผู้ใช้ (local) และใช้โมเดลภาษาแบบ fine-tuned เพื่อเลียนแบบรูปแบบการสนทนาของบุคคลชื่อ **กัปปิตัน** เป้าหมายหลักไม่ใช่การเป็นผู้ช่วยตอบความรู้ทั่วไป แต่เป็นการสร้างคำตอบที่มีคุณลักษณะใกล้ข้อมูลแชทต้นฉบับ ได้แก่:

- ตอบสั้นในรูปแบบแชทไทย
- ใช้คำ การสะกด น้ำเสียง และจังหวะการตอบใกล้กัปปิตัน
- ใช้ประวัติการสนทนาระยะสั้นเพื่อโต้ตอบหลายเทิร์น
- ลดคำตอบแบบผู้ช่วยทางการหรือคำตอบที่แต่งรายละเอียดส่วนตัวขึ้นเอง

ระบบปัจจุบันประกอบด้วย 4 ชั้น:

```text
Instagram chat export
    -> dataset cleaning/session construction
    -> LoRA fine-tuning
    -> FastAPI model runtime + light guard
    -> browser chat interface
```

### 1.2 สถานะทางเทคนิคปัจจุบัน

| รายการ | ค่าปัจจุบัน |
| --- | --- |
| Base model | `Qwen/Qwen3.5-9B` |
| Adapter หลักที่ server โหลดโดยปริยาย | `output/captain-lora` |
| วิธี fine-tuning | LoRA ผ่าน Unsloth |
| การโหลดโมเดล | 4-bit |
| Training label mode | Last assistant-only loss |
| Runtime context | สูงสุด 6 ข้อความล่าสุด |
| Runtime RAG | ไม่มี |
| General fallback | ไม่มี |
| Guard | Light guard |
| Identity policy เริ่มต้น | `normalize` พร้อม retry |
| การเก็บประวัติหน้าเว็บ | Browser `localStorage` |

ดูค่าต้นทางใน [training/train.py](training/train.py), [web_app/server.py](web_app/server.py) และ [scripts/run_server.ps1](scripts/run_server.ps1)

### 1.3 เหตุผลที่ใช้ Qwen/Qwen3.5-9B

`Qwen/Qwen3.5-9B` เป็น model ID ที่กำหนดเป็นค่าเริ่มต้นใน [training/train.py](training/train.py) และใช้เป็นฐานของ adapter ปัจจุบัน เหตุผลเชิงสถาปัตยกรรมของการเลือกโมเดลระดับ 9B ในโปรเจกต์นี้คือ:

- มีขนาดมากพอสำหรับการเรียนรู้ภาษา การรักษาบริบท และรูปแบบการสนทนาที่หลากหลายกว่ารุ่นขนาดเล็กมาก
- สามารถโหลดแบบ 4-bit และ fine-tune ด้วย LoRA เพื่อให้ทำงานบน GPU เครื่องเดียวได้ โดยไม่ต้องอัปเดตพารามิเตอร์ฐานทั้งหมด
- ใช้ chat template แบบ `system/user/assistant` ได้ จึงรองรับ system prompt และประวัติหลายเทิร์นใน runtime

ข้อจำกัดของข้อสรุปนี้คือ repository ไม่มี benchmark เปรียบเทียบ Qwen3.5-9B กับโมเดลฐานหลายรุ่นภายใต้ชุดข้อมูลและคอนฟิกเดียวกัน จึงควรอธิบายว่าเป็น **โมเดลฐานที่เลือกใช้ในระบบปัจจุบัน** ไม่ใช่หลักฐานว่าเป็นโมเดลที่ดีที่สุดโดยทั่วไป

### 1.4 เหตุผลที่ใช้ Fine-tuning แทน RAG

เป้าหมายของ MiniMe คือการเปลี่ยนพฤติกรรมการสร้างภาษาและบุคลิก ไม่ใช่การค้นข้อเท็จจริงจากคลังเอกสาร Fine-tuning จึงตรงกับโจทย์มากกว่า RAG ในประเด็นต่อไปนี้:

- LoRA ปรับ distribution ของคำตอบให้เรียนรู้คำสั้น คำแสลง และรูปแบบการตอบของกัปปิตันโดยตรง
- RAG เหมาะกับการดึงความรู้หรือหลักฐานที่ต้องอ้างอิง แต่บทสนทนาส่วนตัวจำนวนมากไม่มีข้อความที่ควรนำมาใช้เป็นข้อเท็จจริงข้ามบริบท
- การดึงตัวอย่างแชทที่คล้ายกันอาจพาชื่อคน สถานที่ เลข หรือสถานะจากบทสนทนาอื่นมาใส่ใน prompt และเพิ่ม context drift
- ระบบปัจจุบันจึงไม่มีโมดูล retrieval และไม่มีการส่ง retrieved examples เข้าโมเดล ตรวจสอบได้จาก [web_app/server.py](web_app/server.py) และโฟลเดอร์ [minime_core/](minime_core/)

### 1.5 เหตุผลที่ไม่มี General Fallback

General fallback คือการใช้พจนานุกรมหรือคำตอบตายตัวแทนโมเดลเมื่อเจอ prompt บางแบบ แนวทางนี้ถูกถอดออกเพื่อให้:

- คำตอบส่วนใหญ่เป็นผลจากโมเดลจริง ไม่ใช่ lookup table
- การประเมินสะท้อนความสามารถของ fine-tuned model มากขึ้น
- ลดอาการตอบซ้ำคำเดิมจาก fallback แม้บริบทต่างกัน

ข้อยกเว้นคือ **identity finalization** สำหรับคำถามชื่อและตัวตน ซึ่งเป็น policy เฉพาะของระบบ ไม่ใช่ fallback สนทนาทั่วไป รายละเอียดอยู่ในหัวข้อ 5.7

---

## 2. โครงสร้างและการจัดระเบียบข้อมูล (Detailed Project Directory)

### 2.1 แผนผังระดับบนสุด

```text
MiniMe/
├─ data/                         ข้อมูลดิบ ข้อมูลหลัง clean และ JSONL สำหรับ train
├─ minime_core/                  ฟังก์ชันร่วมด้าน UTF-8, text cleanup และ guard
├─ scripts/                      data pipeline และ PowerShell launchers
├─ training/                     LoRA training entry point
├─ web_app/                      FastAPI server และ static frontend
├─ evaluation/                   prompt generation และ evaluation scripts
├─ reports/                      training/evaluation artifacts
├─ output/                       LoRA adapters และ checkpoints (ไม่ควร commit)
├─ diagrams/                     ภาพ/ไฟล์ประกอบสถาปัตยกรรมและงานวิจัย
├─ requirements.txt              Python dependencies
├─ README.md                     คู่มือใช้งานระดับย่อ
└─ PROJECT_OVERVIEW.md           เอกสาร technical specification ฉบับนี้
```

### 2.2 `data/`

| Path | หน้าที่ |
| --- | --- |
| `data/raw_data/` | Instagram chat export ต้นฉบับ รองรับทั้งโครงสร้างเป็นโฟลเดอร์ต่อ conversation และโครงสร้าง JSON แบบ flatten |
| `data/filtered/` | JSON ต่อ conversation หลังแก้ encoding และตัดข้อความระบบ/ขยะ แต่ยังเก็บ `sender`, `content`, `timestamp` |
| `data/output/base_data.jsonl` | sessions ทั้งหมดหลัง merge turns และแยกด้วย time gap พร้อม `source` และ timestamp metadata |
| `data/output/train.jsonl` | sessions สำหรับสร้าง training examples |
| `data/output/val.jsonl` | sessions ช่วงท้ายของแต่ละ source สำหรับ validation |
| `data/curated/general_chat_train.jsonl` | ตัวอย่างสนทนาทั่วไปที่ใช้เป็น training signal เพิ่มเติม |
| `data/curated/general_chat_val.jsonl` | ตัวอย่าง curated สำหรับ validation |

ข้อมูลใน `data/` มีเนื้อหาส่วนตัวและไม่ควร commit หรือเผยแพร่ ดูกติกา ignore ใน [.gitignore](.gitignore)

### 2.3 `minime_core/`

| ไฟล์ | หน้าที่ |
| --- | --- |
| [minime_core/runtime_env.py](minime_core/runtime_env.py) | ตั้ง `PYTHONUTF8`, `PYTHONIOENCODING` และ reconfigure stdout/stderr ให้เสถียรบน Windows |
| [minime_core/text_cleaning.py](minime_core/text_cleaning.py) | cleanup ที่ใช้ร่วมกัน เช่น ลบ think/tag, ลดคำซ้ำ, normalize `เพื่อนนน+`/`เลยยย+`, ตรวจ emoji |
| [minime_core/topic_guard.py](minime_core/topic_guard.py) | training filter ขั้นต่ำ, identity detection/normalization และ runtime garbage validation |
| `minime_core/__init__.py` | ทำให้ directory เป็น Python package |

ไม่มี `rag.py` ในระบบปัจจุบัน และไม่มี retrieval path ใน runtime

### 2.4 `scripts/`

| ไฟล์ | หน้าที่ |
| --- | --- |
| [scripts/config.py](scripts/config.py) | path constants, `ASSISTANT_NAME` และ `SESSION_GAP_MS` |
| [scripts/01_delete_media.py](scripts/01_delete_media.py) | ลบโฟลเดอร์ `audio`, `photos`, `videos` จาก raw export |
| [scripts/02_rename_json.py](scripts/02_rename_json.py) | optional legacy step สำหรับ rename JSON ก่อน flatten; default เป็น preview |
| [scripts/03_flatten_inbox.py](scripts/03_flatten_inbox.py) | optional legacy step สำหรับย้าย JSON ขึ้น root ของ `raw_data`; default เป็น preview |
| [scripts/04_clean_and_filter.py](scripts/04_clean_and_filter.py) | แก้ encoding, ตัดข้อความระบบ/URL และสร้าง conversation JSON ที่สะอาดขึ้น |
| [scripts/05_build_jsonl.py](scripts/05_build_jsonl.py) | sort เวลา, split session, merge consecutive messages และสร้าง `base_data.jsonl` |
| [scripts/06_split_train_val.py](scripts/06_split_train_val.py) | source-preserved chronological split |
| [scripts/run_server.ps1](scripts/run_server.ps1) | launcher ที่ตั้ง UTF-8, adapter, identity policy, access key และเรียก Uvicorn |
| [scripts/run_public_tunnel.ps1](scripts/run_public_tunnel.ps1) | เปิด local server พร้อม Cloudflare quick tunnel |
| [scripts/stop_public_tunnel.ps1](scripts/stop_public_tunnel.ps1) | ปิด process tree ของ server/tunnel ที่เปิดแบบ background |

### 2.5 `training/`

[training/train.py](training/train.py) เป็น entry point เดียวสำหรับ:

- data-check โดยไม่โหลดโมเดล
- สร้าง assistant-turn examples จาก train/val sessions
- รวม curated examples
- โหลด Qwen ผ่าน Unsloth
- ติดตั้ง LoRA adapters
- tokenize และสร้าง last-assistant-only labels
- train/evaluate/save checkpoint
- สร้างรายงาน JSON, CSV และ Markdown ใน `reports/training/`

### 2.6 `web_app/`

| ไฟล์ | หน้าที่ |
| --- | --- |
| [web_app/server.py](web_app/server.py) | FastAPI app, model loading, access control, generation, retry, guard และ SSE endpoint |
| [web_app/static/index.html](web_app/static/index.html) | โครง HTML ของหน้าแชท |
| [web_app/static/app.js](web_app/static/app.js) | room state, localStorage, health polling, SSE parsing และการส่งข้อความ |
| [web_app/static/styles.css](web_app/static/styles.css) | responsive layout และชุดสี Deep Pond / Goldfish Orange |

### 2.7 `evaluation/`

| ไฟล์ | หน้าที่ |
| --- | --- |
| [evaluation/prompts.jsonl](evaluation/prompts.jsonl) | prompt set หลัก 66 ข้อ |
| [evaluation/check_prompts.py](evaluation/check_prompts.py) | ตรวจ schema, duplicate IDs และ verbatim contamination |
| [evaluation/generate_responses.py](evaluation/generate_responses.py) | generate แบบ direct หรือผ่าน runtime server สำหรับ baseline/fine-tuned |
| [evaluation/compute_metrics.py](evaluation/compute_metrics.py) | auto metrics, reply-length reference และ loss/overfitting summary |
| [evaluation/prepare_human_eval.py](evaluation/prepare_human_eval.py) | สร้าง blind A/B CSV, rubric, instructions และ private mapping |
| [evaluation/analyze_human_eval.py](evaluation/analyze_human_eval.py) | วิเคราะห์คะแนน, agreement และ Wilcoxon test |
| [evaluation/analyze_live_chat.py](evaluation/analyze_live_chat.py) | รวมผล live chat โดยให้น้ำหนักผู้ประเมินแต่ละคนเท่ากัน |

### 2.8 `reports/`

| Path | หน้าที่ |
| --- | --- |
| `reports/training/` | training metrics ต่อรันในรูป JSON/CSV/Markdown |
| `reports/evaluation/<run-id>/` | generated responses, auto metrics, blind human eval, live chat และ final summary |
| [reports/evaluation/20260616-141015/final_evaluation_summary.md](reports/evaluation/20260616-141015/final_evaluation_summary.md) | สรุปผลรันหลักล่าสุด |
| [reports/evaluation/20260616-141015/training_loss_curve_2epochs.xlsx](reports/evaluation/20260616-141015/training_loss_curve_2epochs.xlsx) | ตารางและกราฟ training/validation loss |

### 2.9 `output/`

- `output/captain-lora/` คือ adapter หลักที่ server ใช้โดยปริยาย
- `output/candidates/` ใช้เก็บ candidate และ checkpoints ระหว่างทดลอง
- training code ป้องกันการเขียนทับ `output/captain-lora` และ `output/captain-lora-candidate` โดยตรง
- การ promote candidate ไปเป็น adapter หลักยังเป็นขั้นตอนที่ผู้พัฒนาต้องทำหลังประเมินผล ไม่ได้มี promotion script อัตโนมัติ

---

## 3. สถาปัตยกรรมข้อมูลแชทและการทำความสะอาด (Dataset Pipeline & Preprocessing)

### 3.1 Data contracts ระหว่างขั้น

#### Raw Instagram chat message

ฟิลด์ที่ pipeline สนใจคือ `sender_name`, `content`, `timestamp_ms` และ `call_duration` โดยอ่านจาก `messages` ในแต่ละ export part

#### Filtered conversation JSON

```json
[
  {
    "sender": "ชื่อผู้ส่ง",
    "content": "ข้อความหลัง clean",
    "timestamp": 1710000000000
  }
]
```

#### Session JSONL

```json
{
  "source": "conversation.json",
  "session_index": 0,
  "session_start_ms": 1710000000000,
  "session_end_ms": 1710000200000,
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

`source`, `session_index` และ timestamps ใช้สำหรับ split/audit เท่านั้น `tokenize_chat()` ส่งเฉพาะ `messages` เข้า chat template ดังนั้นชื่อ source **ไม่ใช่ข้อความที่โมเดลอ่านหรือใช้คำนวณ loss**

### 3.2 Step 01: ลบ media folders

[scripts/01_delete_media.py](scripts/01_delete_media.py) เดินทุก directory ใต้ `data/raw_data/` และลบ directory ที่ชื่อ `audio`, `photos` หรือ `videos`

- เป็น destructive step และไม่มี preview mode
- ไม่ลบ JSON message files
- มีเป้าหมายเพื่อลดขนาดข้อมูลที่ไม่ใช้ใน text training

### 3.3 Step 02: Rename JSON (optional)

[scripts/02_rename_json.py](scripts/02_rename_json.py) เป็น legacy utility สำหรับตั้งชื่อ JSON ตาม prefix ของ conversation folder

- ไม่จำเป็นสำหรับ layout มาตรฐาน `conversation/message_*.json`
- ถ้าไม่ใส่ `--apply` จะแสดงเฉพาะสิ่งที่จะเปลี่ยน
- ไม่เขียนทับ target ที่มีอยู่แล้ว

### 3.4 Step 03: Flatten Inbox (optional)

[scripts/03_flatten_inbox.py](scripts/03_flatten_inbox.py) ย้าย JSON จาก subfolders ขึ้นมาไว้ที่ `data/raw_data/` และลบ conversation folders หลังย้าย

- default เป็น preview เช่นเดียวกับ Step 02
- ถ้าชื่อซ้ำจะเติม suffix `_2`, `_3`, ...
- Step 04 รองรับทั้ง layout เดิมและ flattened layout จึงไม่จำเป็นต้องรัน Step 02/03 เสมอ

### 3.5 Step 04: Clean and Filter

[scripts/04_clean_and_filter.py](scripts/04_clean_and_filter.py) เป็นชั้น cleanup หลักก่อนสร้าง sessions

#### การแก้ Encoded Text ภาษาไทย

Instagram chat export ที่ใช้ในโปรเจกต์มีข้อความภาษาไทยบางส่วนซึ่ง byte ของ UTF-8 ถูกตีความเป็น latin1 ทำให้แสดงเป็น mojibake ฟังก์ชัน `fix_encoding()` แก้ด้วยลำดับ:

```python
text.encode("latin1").decode("utf-8")
```

ถ้า string ไม่สามารถ encode เป็น latin1 หรือ decode กลับเป็น UTF-8 ได้ ฟังก์ชันจะคืนข้อความเดิม เพื่อไม่ทำลายข้อความที่ถูกต้องอยู่แล้ว กระบวนการนี้ใช้ทั้ง `sender_name` และ `content`

#### การคัดกรองคำตอบและขยะ

`clean_message()` ตัดข้อความต่อไปนี้:

- record ที่ไม่มี `content`
- record ที่มี `call_duration`
- attachment notifications เช่น `sent an attachment` และ `ส่งไฟล์แนบ`
- การแชร์โพสต์/สตอรี่ เช่น `แชร์โพสต์`, `แชร์สตอรี่`, `shared a story`
- call/video notifications เช่น `started an audio call`, `missed a video chat`, `Call ended`, `Audio call started`
- live location, theme change และ quiet mode notifications
- reaction/like notifications ที่ขึ้นต้นด้วย `Reacted ` หรือ `Liked `
- URL ที่ขึ้นต้นด้วย HTTP/HTTPS หรือ domain ที่กำหนด เช่น Facebook, Instagram และ YouTube
- suffix `(edited)`

ถ้าลบ URL แล้วไม่เหลือ content จะทิ้ง record นั้น

#### การรวม export parts และคัด conversation

- รองรับ `message_1.json`, `message_2.json`, ... ใน conversation เดียวและรวม messages ทุก part
- ข้าม group chat ที่มี participants มากกว่า 2 คน
- ข้าม conversation ที่ว่างหลัง cleaning
- ข้าม monologue ที่เหลือผู้ส่งเพียงคนเดียว
- เขียนผลเป็น UTF-8 พร้อม `ensure_ascii=False` ลง `data/filtered/`

### 3.6 Step 05: Message Merging และ Session Splitting

[scripts/05_build_jsonl.py](scripts/05_build_jsonl.py) แปลง filtered conversations เป็น session JSONL

#### Role mapping

- sender ที่ตรงกับ `ASSISTANT_NAME = "กัปปิตัน"` ได้ role `assistant`
- sender อื่นได้ role `user`
- group chats ถูกตัดใน Step 04 แล้ว จึงคาดว่าแต่ละไฟล์มีคู่สนทนา 2 คน

#### การเรียงเวลา

แต่ละ conversation ถูก sort ตาม `timestamp` จากเก่าไปใหม่ก่อนสร้าง session

#### การแบ่ง session

ค่ากำหนดอยู่ใน [scripts/config.py](scripts/config.py):

```python
SESSION_GAP_MS = 3_600_000
```

เมื่อข้อความใหม่ห่างจากข้อความก่อนหน้ามากกว่า 1 ชั่วโมง จะปิด session ปัจจุบันและเริ่ม session ใหม่ กลไกนี้ใช้ gap ระหว่างข้อความติดกัน ไม่ใช่เวลารวมของ session

#### การรวมข้อความเป็น turn

หลังแปลง sender เป็น role แล้ว ถ้าข้อความติดกันมี role เดียวกัน ระบบจะรวม content ด้วยช่องว่างหนึ่งตัว:

```text
"ข้อความแรก" + " " + "ข้อความถัดไป"
```

จึงไม่มี loss boundary ระหว่างข้อความย่อยของคนเดียวกันใน turn เดียว

#### การทำให้ session เริ่มด้วย user

`format_session()` ลบ assistant turns ที่อยู่ต้น session ซ้ำไปเรื่อย ๆ จน turn แรกเป็น `user` เหตุผลคือ training example ต้องมี user context ก่อน target assistant reply

จากนั้นทิ้ง session ที่ไม่มีทั้ง user และ assistant อย่างน้อยหนึ่ง turn

#### Metadata

แต่ละ row เก็บ `source`, `session_index`, `session_start_ms`, `session_end_ms` และ `messages` เพื่อให้ Step 06 แบ่งข้อมูลตาม source และเวลาได้

### 3.7 Step 06: Source-preserved Chronological Split

[scripts/06_split_train_val.py](scripts/06_split_train_val.py) แบ่ง `base_data.jsonl` เป็น train/validation โดยมีหลักดังนี้:

1. group sessions ตาม `source`
2. sort sessions ภายใน source ตาม `session_start_ms`
3. source ที่มีน้อยกว่า `MIN_SESSIONS_FOR_VAL = 10` อยู่ใน train ทั้งหมด
4. source ที่มีอย่างน้อย 10 sessions กันช่วงท้ายประมาณ 10% เป็น validation
5. จำนวน validation ต่อ source คำนวณด้วย `max(1, int(total * 0.10 + 0.5))`
6. train sessions จากทุก source ถูก shuffle ด้วย seed 42
7. validation sessions ไม่ถูก shuffle

แนวทางนี้เรียกว่า **Source-preserved Chronological Split** เพราะ source ขนาดใหญ่ปรากฏทั้ง train และ validation แต่ validation ใช้ session ที่เกิดทีหลัง ช่วยจำลองการตอบข้อความอนาคตของคู่สนทนาเดิมมากกว่าการสุ่มข้อความทั้งหมดปนกัน

#### เหตุผลที่ source ขนาดเล็กอยู่ใน train เท่านั้น

การบังคับแบ่ง source ที่มีเพียงไม่กี่ sessions จะทำให้ validation มีแค่ 1 session และทำให้ข้อมูลของ source นั้นใน train ลดลงมากเมื่อเทียบกับขนาดเดิม ค่า `MIN_SESSIONS_FOR_VAL = 10` จึงเป็น threshold แบบเจาะจงที่เลือกให้:

- source ขนาดใหญ่มีทั้ง train และ validation เพื่อวัดการ generalize ไปยังช่วงเวลาที่ใหม่กว่า
- source ขนาดเล็กยังช่วยเพิ่มความหลากหลายของสไตล์และบริบทใน train
- ไม่ตีความผลจาก validation เพียง 1 session ของ source เล็กว่าเป็นตัวแทนพฤติกรรมของ source นั้น

ข้อแลกเปลี่ยนคือ source ขนาดเล็กไม่มี metric แยกใน validation และคุณภาพของ source เหล่านั้นไม่ถูกวัดโดยตรง กฎนี้จึงไม่ใช่สูตรสากล แต่เป็น design decision ของ dataset ปัจจุบัน หากจำนวน sessions ต่อ source เปลี่ยนมาก ควรทบทวน threshold ใหม่โดยรายงานจำนวน sources ที่มี validation และ train-only ทุกครั้ง

ข้อควรระวัง:

- global ratio อาจไม่เท่ากับ 90/10 พอดี เพราะ source ขนาดเล็กไม่มี validation
- เป็นการลด leakage ทางเวลา แต่ข้อความคล้ายกันจากคู่สนทนาเดิมยังอาจปรากฏทั้งสอง split
- การ split 90/10 ไม่ได้ป้องกัน overfitting ด้วยตัวเอง ต้องดู eval loss และการประเมินสนทนาจริงร่วมด้วย

### 3.8 Snapshot ของ dataset ปัจจุบัน

| รายการ | จำนวน |
| --- | ---: |
| Sessions ใน `base_data.jsonl` | 1,707 |
| Train sessions | 1,545 |
| Validation sessions | 162 |
| Sources ทั้งหมด | 43 |
| Sources ที่มี validation | 22 |
| Sources ที่อยู่ train เท่านั้น | 21 |
| Curated train rows ต้นฉบับ | 130 |
| Curated validation rows | 41 |

ตัวเลขนี้เป็น snapshot ของไฟล์ปัจจุบันและอาจเปลี่ยนเมื่อ rebuild dataset

---

## 4. กระบวนการฝึกฝนแบบจำลอง (Training & LoRA Fine-Tuning)

### 4.1 Input files

[training/train.py](training/train.py) อ่าน:

- `data/output/train.jsonl`
- `data/output/val.jsonl`
- `data/curated/general_chat_train.jsonl`
- `data/curated/general_chat_val.jsonl`

### 4.2 การสร้างหนึ่ง training example

`build_turn_examples()` ไม่ใช้หนึ่ง session เป็นหนึ่ง example แต่สร้าง example ใหม่สำหรับ assistant turn ทุกตัวที่ผ่าน filter:

1. clean ทุก message ด้วย `clean_content()`
2. ตัด content ว่างหรือมี URL/image extension ตาม `is_usable_content()`
3. เดินหา assistant message ทีละตัว
4. ตัด target reply ที่ยาวเกิน `MAX_COMPLETION_CHARS = 60`
5. ใช้ข้อความก่อน target สูงสุด 8 messages เป็น context
6. ตรวจว่า context สุดท้ายเป็น user
7. ตัด target ที่มีเบอร์โทรส่วนตัวซึ่งไม่ปรากฏใน context
8. สร้าง example เป็น `[context..., target assistant]`

แม้ตัวแปรชื่อ `MAX_CONTEXT_TURNS` แต่ implementation slice จากรายการ messages หลัง merge แล้ว จึงหมายถึง **สูงสุด 8 role messages** ไม่ใช่ 8 คู่ user-assistant

Training filter ปัจจุบันตั้งใจให้เบา โดย `training_skip_reason()` ตัดเฉพาะ:

- ไม่มี user context ก่อน target
- target มี phone-like number ที่ไม่ได้ grounded ใน visible context

ไม่ได้ตัดชื่อคน สถานที่ คำตอบ generic หรือ private context แบบกว้าง เพราะ filter รุ่นที่เข้มกว่านี้เคยทำให้ training signal ลดและบุคลิกเสียได้

### 4.3 Curated Data

ไฟล์ [data/curated/general_chat_train.jsonl](data/curated/general_chat_train.jsonl) และ [data/curated/general_chat_val.jsonl](data/curated/general_chat_val.jsonl) เป็นตัวอย่างควบคุมสำหรับ prompt ทั่วไป เช่น identity, greeting, อาหาร เกม ท่องเที่ยว อารมณ์ และ privacy/status

วัตถุประสงค์คือ:

- เพิ่มสัญญาณสำหรับ prompt ทั่วไปที่ raw chat อาจมีไม่สมดุล
- กำหนดความสั้นและน้ำเสียงที่ต้องการ
- ลดการพึ่ง runtime fallback

`CURATED_REPEAT = 2` หมายถึง curated train examples 130 rows ถูกนำมาต่อใน training rows สองชุด รวม 260 examples ส่วน curated validation 41 rows ใช้ครั้งเดียว

Curated examples ไม่ผ่าน `training_skip_reason()` และไม่มี source cap จึงต้อง review เนื้อหาเองก่อน train ทุกครั้ง Curated ไม่ใช่ RAG และไม่ถูกค้นมาใช้ตอนตอบ runtime

### 4.4 Snapshot หลังสร้าง assistant-turn examples

จาก [reports/training/training_metrics_20260610-162705.json](reports/training/training_metrics_20260610-162705.json):

| รายการ | จำนวน |
| --- | ---: |
| Raw train assistant examples | 3,445 |
| Raw validation assistant examples | 437 |
| Curated train หลัง repeat | 260 |
| Curated validation | 41 |
| Final train examples | 3,705 |
| Final validation examples | 478 |
| Raw train ที่ถูกตัดเพราะยาว | 13 |
| Raw validation ที่ถูกตัดเพราะยาว | 7 |
| Raw train ที่ถูกตัดเพราะ personal number | 3 |
| Raw validation ที่ถูกตัดเพราะ personal number | 1 |

### 4.5 การโหลดโมเดลและหน่วยความจำ

Unsloth โหลดโมเดลด้วย:

```python
FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen3.5-9B",
    max_seq_length=2048,
    load_in_4bit=True,
    dtype=None,
)
```

4-bit quantization ลด VRAM ที่ใช้เก็บ base weights ส่วน LoRA adapters ยังคงเป็นพารามิเตอร์ที่ฝึกได้ `dtype=None` ให้ Unsloth/PyTorch เลือกชนิดที่เหมาะกับ GPU และ Trainer เลือก BF16 ถ้ารองรับ มิฉะนั้นใช้ FP16

### 4.6 โครงสร้าง LoRA

| Parameter | ค่า |
| --- | ---: |
| Rank (`r`) | 16 |
| Alpha | 32 |
| Dropout | 0.05 |
| Bias | none |
| Gradient checkpointing | `unsloth` |
| Random state | 42 |

Target projection modules:

```text
q_proj, k_proj, v_proj, o_proj,
gate_proj, up_proj, down_proj
```

กลุ่มแรกครอบคลุม attention projections และกลุ่มหลังครอบคลุม MLP projections จึงให้ LoRA ปรับทั้งการใช้บริบทและรูปแบบการสร้างคำ โดยไม่แก้ base weights ทั้งหมด

### 4.7 Chat template

Training template ใช้ token รูปแบบ Qwen:

```text
<|im_start|>system ... <|im_end|>
<|im_start|>user ... <|im_end|>
<|im_start|>assistant ... <|im_end|>
```

Assistant content ถูกครอบด้วย Jinja `{% generation %}` เพื่อให้ tokenizer คืน `assistant_masks`

### 4.8 Last Assistant-Only Loss

เป้าหมายคือให้โมเดล **อ่าน context ทั้งหมด แต่คำนวณ loss เฉพาะ target assistant ล่าสุด**

#### ขั้นตอน tokenization

`tokenize_chat()` เรียก `apply_chat_template()` ด้วย:

- `return_assistant_tokens_mask=True`
- `truncation=True`
- `max_length=2048`
- `add_generation_prompt=False`

ผลลัพธ์มี `input_ids`, `attention_mask` และ `assistant_masks`

#### ขั้นตอนสร้าง labels

`build_last_assistant_labels()` ทำงานดังนี้:

1. สร้าง `labels` ยาวเท่า `input_ids` และใส่ `-100` ทุกตำแหน่ง
2. หา token สุดท้ายที่ `assistant_mask=True`
3. เดินย้อนกลับจนถึง token แรกของ contiguous assistant span สุดท้าย
4. copy `input_ids` เฉพาะ span นั้นไปยัง `labels`
5. ถ้า token ถัดไปเป็น EOS หรือ `<|im_end|>` ให้เปิด loss ที่ end token ด้วย

ดังนั้น:

- system/user tokens มี label `-100`
- assistant replies ที่อยู่ใน context มี label `-100`
- assistant reply สุดท้ายและ end token เป็นส่วนที่คำนวณ cross-entropy loss

#### เหตุผลของการออกแบบ

- โมเดลเห็นประวัติ user และ assistant ก่อนหน้า จึงใช้บริบทเพื่อทำนายคำตอบได้
- ไม่บังคับให้โมเดลจำลองคำตอบ assistant เก่าซ้ำทุกครั้งใน example เดียว
- ลด loss signal จาก private details ที่อาจปรากฏใน assistant context
- ทำให้โจทย์ชัดว่า `context ปัจจุบัน -> คำตอบกัปปิตันเป้าหมาย`

ข้อแลกเปลี่ยนคือจำนวน supervised tokens ต่อ example ลดลง และ context assistant ที่ไม่ถูกคำนวณ loss ยังสามารถมีผลต่อ representation ที่ใช้ทำนาย target ได้

### 4.9 Data collator

`AssistantOnlyDataCollator` pad แต่ละ batch ไปยัง sequence ที่ยาวที่สุดใน batch:

- `input_ids` pad ด้วย tokenizer pad token หรือ EOS ถ้าไม่มี pad token
- `attention_mask` pad ด้วย 0
- `labels` pad ด้วย `-100`

จึงไม่มี loss บน padding tokens

### 4.10 Trainer configuration

| Parameter | ค่า |
| --- | ---: |
| Max sequence length | 2048 |
| Context messages | 8 |
| Max target chars | 60 |
| Epochs | 2 |
| Per-device batch size | 1 |
| Gradient accumulation | 8 |
| Effective update batch | 8 examples ต่อ device |
| Learning rate | `2e-4` |
| Scheduler | cosine |
| Warmup ratio | 0.05 |
| Weight decay | 0.01 |
| Optimizer | `adamw_8bit` |
| Packing | false |
| Logging | ทุก 50 steps |
| Evaluation | ทุก 100 steps |
| Checkpoint save | ทุก 100 steps |
| Save total limit | 10 |
| Best metric | `eval_loss` |
| Greater is better | false |

### 4.11 Best checkpoint และการบันทึกผล

`load_best_model_at_end=True` ทำให้ Trainer โหลด weights ของ checkpoint ที่มี `eval_loss` ต่ำที่สุดเมื่อ training จบ จากนั้น `model.save_pretrained(OUTPUT_DIR)` และ `tokenizer.save_pretrained(OUTPUT_DIR)` บันทึก state ที่โหลดอยู่ที่ root output directory

การเลือก best checkpoint นี้อิง **validation loss เท่านั้น** ไม่ได้เลือกจากคะแนน persona, relevance หรือ live chat จึงต้องประเมิน candidate checkpoints เพิ่มถ้าต้องการเลือกจากคุณภาพสนทนาจริง

### 4.12 Output protection

[training/train.py](training/train.py) ปฏิเสธการ train ลง:

- `output/captain-lora`
- `output/captain-lora-candidate`

ค่าเริ่มต้นเขียนไปที่ `output/candidates/captain-lora-20260610-minfilter` และจะลบ candidate เดิมได้เมื่อ `MINIME_OVERWRITE_OUTPUT=1` เฉพาะ path ที่กำหนดว่า overwritable เท่านั้น

### 4.13 Training reports

หลัง train ระบบเขียน:

- JSON: config, data counts, best checkpoint, final metrics และ log history
- CSV: loss/eval loss/learning rate ตาม step
- Markdown: summary และ loss table

ไฟล์อยู่ใน [reports/training/](reports/training/)

---

## 5. สถาปัตยกรรมรันไทม์และระบบป้องกัน (Runtime & Safety Guard)

### 5.1 FastAPI lifecycle

[web_app/server.py](web_app/server.py) สร้าง FastAPI app และ mount static files ที่ `/static`

เมื่อ startup:

1. เปิด daemon thread เรียก `load_model_once()`
2. ตรวจว่า adapter path มีอยู่
3. โหลด `output/captain-lora` หรือ path จาก `MINIME_ADAPTER_PATH` แบบ 4-bit
4. เรียก `FastLanguageModel.for_inference()`
5. ติดตั้ง system-aware chat template
6. อัปเดตสถานะ `loading -> ready` หรือ `error`

หน้าเว็บ poll `/health` จนโมเดลพร้อม

### 5.2 Runtime message selection

`MAX_HISTORY_MESSAGES = 6` ใช้ทั้ง server และ frontend

`recent_chat_messages()`:

- เก็บเฉพาะ role `user`/`assistant`
- ตัด content ว่าง
- ตัด message ที่ `flagged=true`
- เลือก 6 messages ล่าสุด

จากนั้นเพิ่ม system prompt ด้านหน้า จึงมีได้สูงสุด 7 message objects ใน generation input: system 1 + chat history 6

### 5.3 Runtime system prompt

System prompt กำหนดให้:

- ตอบสั้นแบบแชทไทยในสไตล์กัปปิตัน
- อิงบทสนทนาล่าสุด
- ถ้าขาดข้อมูลสำคัญสามารถถามกลับสั้น ๆ แต่ไม่ถามวน
- ห้ามเดาชื่อคน สถานที่ กิจกรรม ความสัมพันธ์ หรือสถานะที่ user ไม่ได้กล่าว

System prompt เป็น runtime policy และไม่ได้ถูกเพิ่มเข้า raw training examples

### 5.4 Generation configuration

Request schema จำกัด:

| Parameter | ค่าเริ่มต้น | ช่วงที่ยอมรับ |
| --- | ---: | ---: |
| `max_new_tokens` | 24 | 1-24 |
| `temperature` | 0.0 | 0.0-2.0 |
| `top_p` | 1.0 | >0-1.0 |

Generation ปกติใช้:

- greedy decoding เมื่อ temperature = 0
- `repetition_penalty = 1.3`
- `no_repeat_ngram_size = 3`
- EOS และ `<|im_end|>` เป็น stop tokens

ระบบใช้ `generation_lock` แบบ non-blocking เพื่อให้มี generation ครั้งเดียวบน GPU ถ้ามี request ซ้อนจะส่ง `Model is busy`

### 5.5 SSE response flow

Endpoint คือ `POST /api/chat/stream` และตอบด้วย `text/event-stream`

ลำดับ event ที่เป็นไปได้:

- `status`: model ยังโหลดอยู่
- `error`: model/generation/guard error
- `token`: คำตอบที่ผ่านแล้ว
- `done`: metadata เช่น `ok`, `flagged`, `sanitized`, `guard_reason`

Implementation ปัจจุบัน generate คำตอบทั้งหมดก่อน แล้วส่งคำตอบเต็มใน `token` event หนึ่งครั้ง ไม่ใช่ token-by-token decoding จริง แม้ transport จะใช้ SSE

### 5.6 Light Guard

Light guard แบ่งเป็น cleanup และ validation

#### `clean_generated_reply()`

อยู่ใน [minime_core/text_cleaning.py](minime_core/text_cleaning.py) และทำงานดังนี้:

- strip ช่องว่างหัวท้าย
- ลบ `<think>...</think>` และ think tags ที่หลงเหลือ
- ลบ bracket tags ความยาว 1-20 ตัวอักษร
- ลด repeated token ที่ซ้ำติดกัน 4 ครั้งขึ้นไป
- แปลง `เพื่อนนน+ -> เพื่อนน`
- แปลง `เลยยย+ -> เลยย`
- ลดช่องว่างซ้ำ

#### `garbage_reply_reason()`

อยู่ใน [minime_core/topic_guard.py](minime_core/topic_guard.py) และคืน reason เมื่อพบ:

| Reason | เงื่อนไข |
| --- | --- |
| `empty` | หลัง clean ไม่เหลือข้อความ |
| `replacement_char` | มี Unicode replacement character `U+FFFD` |
| `cjk` | มีอักขระใน CJK Unified Ideographs ranges ที่กำหนด |
| `bad_generation` | มี token ที่ blacklist เช่น `吃什么去啊`, `客气吧`, `kappitan`, `kappitton`, `captain`, `kongkai`, `ไอแพน`, `คุณายาว` |
| `app_package` | มี string คล้าย package name เช่น `abc.def.ghi` |
| `long_number` | มีเลขติดกันอย่างน้อย 8 หลัก |
| `personal_number` | ตรงรูปแบบเบอร์โทรที่ขึ้นต้นด้วย 0 |
| `emoji_spam` | เป็น emoji ล้วน หรือมี emoji อย่างน้อย 3 ตัว |

มีความต่างด้านการสะกดที่ต้องระวัง: `GARBAGE_RETRY_SYSTEM_HINT` ใน server ยกตัวอย่างคำว่า `คูณายาว` แต่ `BAD_GENERATION_RE` ใน guard บล็อก string `คุณายาว` ตามตัวอักษรจริง ดังนั้น `คูณายาว` ไม่ได้ถูก regex นี้จับโดยตรงหากไม่เข้าเงื่อนไขขยะอื่น

#### `validate_reply()`

1. clean reply
2. apply identity normalization
3. reject ถ้า `garbage_reply_reason()` คืนค่า
4. reject bracket tag ที่ยังเหลือ
5. reject ถ้ายาวเกิน `MAX_REPLY_CHARS = 70`
6. คืนข้อความที่ผ่าน

`validate_reply()` รับ `context_text` แต่ implementation ปัจจุบันยังไม่ได้ใช้ argument นี้ใน general validation จึงไม่มี regex block ชื่อ/สถานที่/private context สำหรับทุกคำตอบ การลด context drift ทั่วไปพึ่ง system prompt, fine-tuned model และ garbage guard เป็นหลัก

### 5.7 Garbage retry

ถ้าคำตอบแรกเข้า `garbage_reply_reason()`:

1. เพิ่ม `GARBAGE_RETRY_SYSTEM_HINT`
2. generate ใหม่แบบ sampling ด้วย temperature 0.7 และ top-p 0.9
3. retry สูงสุด 2 ครั้ง
4. ถ้ายังไม่ผ่าน `validate_reply()` จะ reject โดยไม่มี general fallback

Hint กำหนดให้ตอบภาษาไทย ห้ามอังกฤษ/จีนและคำประหลาด แต่ไม่ได้กำหนดคำตอบตายตัว

### 5.8 Identity Policy และ Retry Logic

Identity แบ่งเป็น 2 กลุ่ม:

- name identity เช่น `ชื่ออะไร`, `คุณคือใคร`, `เรียกอะไรดี`
- bot identity เช่น `เป็นบอทหรอ`, `เป็น AI ไหม`

#### `needs_identity_retry()`

สำหรับ name identity จะ retry เมื่อ:

- ไม่มีคำว่า `กัปปิตัน`
- normalized reply ยาวเกิน 16 ตัวอักษร
- มีเลข
- มี private context, number context, phone number หรือ specific place pattern

สำหรับ bot identity จะ retry เมื่อ:

- ตอบปฏิเสธสั้น ๆ อย่างเดียว เช่น `ไม่ใช่`
- ไม่มีสัญญาณยอมรับว่าเป็น AI/bot
- normalized reply ยาวเกิน 18 ตัวอักษร
- มี private context

#### Identity system hints

- `NAME_IDENTITY_RETRY_SYSTEM_HINT` ขอให้ตอบ `กัปปิตัน` หรือ `กัปปิตันก็ได้`
- `BOT_IDENTITY_RETRY_SYSTEM_HINT` ขอให้ตอบสั้น เช่น `ใช่ๆ` หรือ `ก็ประมาณนั้น` และห้ามลากไปเรื่องอื่น
- identity retry จำกัด `max_new_tokens` เหลือ 8

#### Normalize

นโยบายกำหนดด้วย `MINIME_IDENTITY_POLICY`:

| Policy | พฤติกรรม |
| --- | --- |
| `normalize` | ค่าเริ่มต้น แก้ variant เช่น `กัปปิ`, `กัปตัน`, `kappitton`, `captain`, `cap`, `kap` และทำให้ name identity จบเป็น `กัปปิตัน` |
| `force` | บังคับ name identity เป็น `กัปปิตัน` และ bot identity เป็น `ก็ประมาณนั้นแหละ` |
| `off` | ไม่ normalize และไม่ deterministic-finalize identity |

#### Finalization

ถ้า retry แล้วยังไม่ผ่านและ policy ไม่ใช่ `off`:

- name identity คืน `กัปปิตัน`
- bot identity คืน `ก็ประมาณนั้นแหละ`

นี่เป็น deterministic identity policy เฉพาะ domain ไม่ใช่ general fallback สำหรับ prompt อื่น

### 5.9 Debug mode

ถ้า request ส่ง `debug=true`, `done` event จะมี:

- raw reply รอบสุดท้าย
- first raw reply
- cleaned/final reply
- retry count/reason
- identity retry reason
- garbage reason ล่าสุด

Frontend ปกติไม่ได้เปิด debug; evaluation runtime mode เปิดเพื่อเก็บหลักฐาน

### 5.10 Access control

ถ้าตั้ง `MINIME_ACCESS_KEY`:

- middleware ป้องกัน endpoint ยกเว้นหน้า `/` และ static files
- user ส่ง key ผ่าน query string ที่หน้าแรก
- server เก็บ key ใน HttpOnly cookie ชื่อ `minime_access`
- cookie อายุ 7 วันและใช้ `SameSite=Lax`

ถ้าไม่ตั้ง key ระบบ local server เปิดโดยไม่มี authentication

---

## 6. เว็บอินเทอร์เฟซและการจัดเก็บประวัติ (Frontend & Local Storage)

### 6.1 Room model

[web_app/static/app.js](web_app/static/app.js) เก็บ state ของหลายห้องแชท:

```javascript
{
  id,
  title,
  messages,
  createdAt,
  updatedAt
}
```

ห้องใหม่ใช้ชื่อ `New Chat` และเปลี่ยน title จากข้อความ user แรก สูงสุด 34 ตัวอักษร

### 6.2 Local Storage

- key ปัจจุบันคือ `minime.chat.rooms.v3`
- legacy keys `v1` และ `v2` ถูกลบเมื่อโหลดหน้า
- `saveRooms()` serialize rooms ทั้งหมดเป็น JSON ลง browser `localStorage`
- server ไม่มี database สำหรับเก็บ chat history
- ในแต่ละ request frontend ส่งเฉพาะ 6 messages ล่าสุดที่ไม่ pending และไม่ flagged

ความเป็นส่วนตัวของแนวทางนี้:

- ประวัติเต็มอยู่ใน browser profile ของเครื่องผู้ใช้ ไม่ถูกเขียนเป็นไฟล์บน server โดยแอป
- 6 messages ล่าสุดยังถูกส่งไปยัง FastAPI/GPU เพื่อ generate
- localStorage ไม่ได้เข้ารหัส ผู้ที่เข้าถึง browser profile/origin เดียวกันอาจอ่านข้อมูลได้

### 6.3 Model health และการส่งข้อความ

- `pollHealth()` เรียก `/health` ทุก 1.6 วินาทีจนสถานะ `ready` หรือ `error`
- ปุ่มส่งถูก disable ระหว่าง model loading หรือ generation
- Enter ส่งข้อความ; Shift+Enter ขึ้นบรรทัดใหม่
- frontend parse SSE events และอัปเดต assistant bubble
- flagged replies ไม่ถูกส่งกลับเป็น history ใน request ถัดไป

### 6.4 Frontend cleanup

`cleanAssistantText()` ลบ bracket emotion tags, repeated tokens และช่องว่างซ้ำอีกชั้นก่อนแสดงผล เป็น defense-in-depth แยกจาก server cleanup

### 6.5 Deep Pond & Goldfish Orange

Design tokens อยู่ใน [web_app/static/styles.css](web_app/static/styles.css):

| Token | สี | บทบาท |
| --- | --- | --- |
| `--deep-pond` | `#123232` | พื้นหลังหลัก/identity ของแอป |
| `--goldfish-orange` | `#f46a21` | user bubble และ primary action |
| `--fin-gold` | `#f7b733` | focus, status และ accent |
| `--pearl-white` | `#fff7ec` | ข้อความหลัก |
| `--pond-green` | `#6e8f5b` | ready status |
| `--water-glass` | `#d7e8e4` | border/translucent elements |

แนวคิดคือใช้พื้นสีเขียวเข้มเป็นสภาพแวดล้อมหลักและส้มปลาทองเป็นสี action/bubble โดยใช้ border radius 8px และ responsive sidebar สำหรับจอเล็กกว่า 820px

---

## 7. กรอบการประเมินผลและการทดสอบ (Evaluation Framework)

### 7.1 Prompt set

[evaluation/prompts.jsonl](evaluation/prompts.jsonl) มี 66 prompts ใน 8 หมวด:

| Category | จำนวน |
| --- | ---: |
| `identity` | 5 |
| `bot_identity` | 3 |
| `greeting` | 10 |
| `food_game_travel` | 13 |
| `emotion_support` | 7 |
| `privacy_status` | 2 |
| `open_ended` | 11 |
| `multi_turn` | 15 |

### 7.2 Prompt validation และ contamination check

[evaluation/check_prompts.py](evaluation/check_prompts.py) ตรวจ:

- JSONL parse ได้
- มี `id`, `category`, `turns`
- role ถูกต้องและ turn สุดท้ายเป็น user
- ID ไม่ซ้ำ
- category อยู่ใน allowlist
- prompt content ที่ยาวอย่างน้อย 10 ตัวอักษรไม่ตรงกับ message ใน train/val แบบ verbatim

คำว่า “ไม่ซ้ำกับข้อมูลฝึก” ในรายงานจึงหมายถึง **ไม่พบ exact string match ตาม threshold นี้** ไม่ได้หมายถึงผ่าน semantic similarity หรือ n-gram contamination test และข้อความสั้นกว่า 10 ตัวอักษรถูกยกเว้นเพราะคำแชททั่วไปซ้ำกันตามธรรมชาติ

### 7.3 Response generation modes

[evaluation/generate_responses.py](evaluation/generate_responses.py) รองรับ:

#### Direct mode

- โหลด fine-tuned adapter หรือ base model โดยตรงผ่าน Unsloth
- ใช้ system prompt, retry, identity policy และ guard logic ให้ใกล้ server
- เหมาะกับ controlled baseline/fine-tuned comparison

#### Runtime mode

- เรียก `/api/chat/stream` ของ server จริง
- เปิด `debug=true`
- วัด behavior ที่รวม server path จริง

Generation ปกติเป็น deterministic เมื่อ temperature = 0 แต่ garbage retry ใช้ sampling จึงไม่รับประกันว่ารันซ้ำทุกครั้งจะได้คำตอบเดียวกันหากเกิด retry

### 7.4 Automatic metrics

[evaluation/compute_metrics.py](evaluation/compute_metrics.py) คำนวณ:

- guard rejection rate
- mean/median reply length
- reply-length ratio เทียบ raw validation reference
- long reply, output artifact, emoji spam, CJK และ bad-token rates
- identity accuracy/retry rate
- generic reply rate สำหรับ open-ended prompts
- character-level Distinct-1/Distinct-2
- average latency
- training/eval loss table และ matched overfitting gap

Reply-length reference ใช้ raw validation assistant targets หลังผ่าน training filters 437 คำตอบ ไม่รวม curated และเป็น corpus-level reference ไม่ใช่ reference answer ที่จับคู่กับแต่ละ prompt

### 7.5 Blind Human A/B Test

[evaluation/prepare_human_eval.py](evaluation/prepare_human_eval.py) สร้าง blind CSV โดย:

- เปรียบเทียบ `finetuned` กับ `baseline`
- randomize ว่าแต่ละ prompt จะแสดง model ใดเป็น A/B ด้วย seed 42
- ไม่เผย mapping จนประเมินเสร็จ
- ให้คะแนน 1-5 แยก A/B

มิติหลัก:

- Persona Consistency
- Style Similarity
- Relevance
- Context Consistency เฉพาะ multi-turn

Captain Similarity Score:

```text
0.45 * persona + 0.35 * style + 0.20 * relevance
```

[evaluation/analyze_human_eval.py](evaluation/analyze_human_eval.py) คำนวณ:

- mean และ standard deviation
- prompt-level win/tie/loss
- pairwise Quadratic Weighted Kappa
- interval Krippendorff's Alpha
- two-sided Wilcoxon signed-rank โดยเฉลี่ย raters ต่อ prompt ก่อน
- exact sign-permutation p-value และ rank-biserial effect size

ผู้ประเมินทุกคนใช้ A/B assignment ชุดเดียวกัน แม้ assignment รวมสมดุล 35/31 จึงยังมีความเสี่ยง position bias บางส่วน

### 7.6 Live Chat Evaluation

[evaluation/analyze_live_chat.py](evaluation/analyze_live_chat.py) วิเคราะห์ session ที่ผู้ประเมินสนทนากับ fine-tuned model จริง โดยเก็บ:

- จำนวน user prompts
- Captain similarity 1-5
- Context following 1-5
- Problem level 1-5 โดยต่ำกว่าดีกว่า
- acceptable/unacceptable response counts

คะแนนหลักคำนวณค่าเฉลี่ยต่อ evaluator ก่อน แล้วจึงเฉลี่ย evaluator ทุกคน เพื่อไม่ให้คนที่ทำหลาย sessions มีน้ำหนักมากกว่าคนอื่น

Live chat ปัจจุบันไม่มี baseline condition และไม่มี transcript ราย turn จึงใช้บอกคุณภาพเชิงพรรณนาของ fine-tuned model แต่ใช้ทดสอบความแตกต่างกับ baseline หรือ audit คำตอบย้อนหลังทีละ turn ไม่ได้

### 7.7 ผลล่าสุด: Run `20260616-141015`

รายงานหลัก: [final_evaluation_summary.md](reports/evaluation/20260616-141015/final_evaluation_summary.md)

#### Training summary

| Metric | ค่า |
| --- | ---: |
| Best checkpoint | `checkpoint-900` |
| Best eval/validation loss | 3.3519 |
| Final train loss | 2.9421 |
| Epochs | 2 |
| Gap เริ่มเกิน 1.0 | step 700 |
| Maximum matched gap | 1.2167 ที่ step 800 |

Validation loss คือ eval loss ในรายงานนี้ เพราะ Trainer ประเมินบน validation dataset

Matched gap เป็น heuristic ที่จับ eval loss กับ train loss ล่าสุดที่ step ไม่เกิน eval step ไม่ใช่ formal generalization bound สัญญาณ gap มากขึ้นช่วงท้ายบ่งชี้ความเสี่ยง overfitting แต่ไม่ควรใช้แทน human evaluation

กราฟ [training_loss_curve_2epochs.xlsx](reports/evaluation/20260616-141015/training_loss_curve_2epochs.xlsx) ใช้ helper grid 0.1 epoch สำหรับการแสดงแกนและ interpolation พร้อม edge hold; ตาราง raw logged values ในไฟล์เป็นข้อมูลอ้างอิงหลัก

#### Automatic comparison

| Metric | Fine-tuned | Baseline |
| --- | ---: | ---: |
| ผ่าน guard | 65/66 | 58/66 |
| Guard rejection rate | 1.52% | 12.12% |
| Mean reply length | 16.0 | 44.4 ตัวอักษร |
| Reply-length ratio | 1.0097 | 2.8018 |
| Identity accuracy | 100% | 100% |
| Generic open-ended rate | 0% | 71.43% |
| Average latency | 1,191.5 ms | 1,989.7 ms |

Identity accuracy รวมผลจาก identity retry/normalization/finalization จึงไม่ใช่การวัด raw model output เพียงอย่างเดียว

#### Blind Human A/B

ผู้ประเมิน 8 คน ให้คะแนนครบ 66 prompts

| Metric (1-5) | Fine-tuned | Baseline | ผลต่าง |
| --- | ---: | ---: | ---: |
| Captain Similarity | 3.95 | 2.28 | +1.67 |
| Persona Consistency | 3.90 | 1.87 | +2.03 |
| Style Similarity | 3.99 | 2.11 | +1.88 |
| Relevance | 3.99 | 3.49 | +0.50 |
| Context Consistency | 4.73 | 4.62 | +0.11 |

Persona, style และ relevance แตกต่างอย่างมีนัยสำคัญ (`p < 0.0001`) ส่วน context consistency ยังไม่พบความแตกต่างอย่างมีนัยสำคัญ (`p = 0.1328`)

Agreement ระหว่างผู้ประเมินของ fine-tuned model อยู่ระดับ Fair/Slight และ Krippendorff's Alpha ต่ำในหลายมิติ จึงต้องรายงานข้อจำกัดของ rubric interpretation ควบคู่ผลเฉลี่ย

#### Live chat

| รายการ | ค่า |
| --- | ---: |
| Evaluators | 8 |
| Sessions | 22 |
| User prompts | 277 |
| Captain similarity | 3.33 ± 0.98 |
| Context following | 3.44 ± 1.01 |
| Problem level | 2.85 ± 0.75 |
| Acceptable responses | 185/277 (66.79%) |
| Unacceptable responses | 92/277 (33.21%) |

ผล live chat ต่ำกว่า impression จาก fixed prompts และแสดงว่าคำตอบประมาณหนึ่งในสามยังถูกจัดว่า unacceptable ในการสนทนาจริง

### 7.8 ข้อสรุปที่รายงานได้และไม่ได้

รายงานได้:

- Fine-tuning เพิ่ม persona/style similarity เทียบ baseline ใน prompt set นี้
- Fine-tuned model ตอบสั้นใกล้ raw validation reference มากกว่า baseline
- Relevance ดีขึ้น แต่ผลต่างเล็กกว่าบุคลิกและสไตล์
- Live chat มี acceptable rate ประมาณสองในสาม

ยังไม่ควรสรุปว่า:

- context handling ดีกว่า baseline อย่างมีนัยสำคัญ
- ผลใช้แทนผู้ใช้ทุกกลุ่มได้
- identity accuracy 100% มาจาก model weights ล้วน เพราะ runtime policy มีส่วน
- checkpoint ที่ eval loss ต่ำสุดต้องเป็น checkpoint ที่คุยดีที่สุดเสมอ

---

## 8. คู่มือใช้งานสำหรับนักพัฒนา

### 8.1 Environment

แนะนำ Python 3.11, Windows และ CUDA GPU

```powershell
python -m venv captain-env
captain-env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 8.2 Rebuild dataset

สำหรับ raw folder layout ปกติ:

```powershell
captain-env\Scripts\python.exe scripts\01_delete_media.py
captain-env\Scripts\python.exe scripts\04_clean_and_filter.py
captain-env\Scripts\python.exe scripts\05_build_jsonl.py
captain-env\Scripts\python.exe scripts\06_split_train_val.py
```

Step 02/03 ใช้เฉพาะเมื่อจำเป็นต้อง flatten และควรรัน preview ก่อน `--apply`

### 8.3 Data check ก่อน train

```powershell
captain-env\Scripts\python.exe training\train.py --data-check-only
```

คำสั่งนี้สร้าง/filter examples และพิมพ์ counts โดยไม่โหลดโมเดล

### 8.4 Train candidate

PowerShell:

```powershell
$env:MINIME_BASE_MODEL="Qwen/Qwen3.5-9B"
$env:MINIME_OUTPUT_DIR="output/candidates/captain-lora-next"
captain-env\Scripts\python.exe training\train.py
```

ถ้าจะ overwrite candidate path ที่ code อนุญาต:

```powershell
$env:MINIME_OVERWRITE_OUTPUT="1"
captain-env\Scripts\python.exe training\train.py
```

อย่า train ทับ `output/captain-lora` ก่อน candidate ผ่าน evaluation

### 8.5 Start server

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_server.ps1
```

ระบุ adapter/policy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_server.ps1 `
  -AdapterPath output\captain-lora `
  -IdentityPolicy normalize `
  -Port 8000
```

เปิด `http://127.0.0.1:8000`

### 8.6 Public tunnel

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_public_tunnel.ps1 -DownloadCloudflared
```

Background mode:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_public_tunnel.ps1 -DownloadCloudflared -Background
```

หยุด:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\stop_public_tunnel.ps1
```

### 8.7 Evaluation workflow

```powershell
captain-env\Scripts\python.exe evaluation\check_prompts.py
```

Generate fine-tuned:

```powershell
captain-env\Scripts\python.exe evaluation\generate_responses.py `
  --adapter output\captain-lora `
  --label finetuned
```

Generate baseline ใน run เดียวกัน:

```powershell
captain-env\Scripts\python.exe evaluation\generate_responses.py `
  --base-only `
  --label baseline `
  --run-dir <RUN_ID>
```

คำนวณ auto metrics และเตรียม human eval:

```powershell
captain-env\Scripts\python.exe evaluation\compute_metrics.py --run-dir <RUN_ID>
captain-env\Scripts\python.exe evaluation\prepare_human_eval.py --run-dir <RUN_ID>
```

วิเคราะห์ scored CSVs:

```powershell
captain-env\Scripts\python.exe evaluation\analyze_human_eval.py `
  --run-dir <RUN_ID> `
  --labels finetuned baseline `
  --eval-csvs rater1.csv rater2.csv rater3.csv
```

### 8.8 Environment variables

| Variable | ใช้โดย | หน้าที่ |
| --- | --- | --- |
| `MINIME_BASE_MODEL` | training | override base model ID |
| `MINIME_OUTPUT_DIR` | training | candidate output path |
| `MINIME_OVERWRITE_OUTPUT` | training | เปิดการลบ candidate เดิมเมื่อค่าเป็น `1` |
| `MINIME_ADAPTER_PATH` | server | adapter ที่ runtime โหลด |
| `MINIME_IDENTITY_POLICY` | server/guard | `normalize`, `force`, `off` |
| `MINIME_ACCESS_KEY` | server | เปิด optional access control |
| `PYTHONUTF8` | CLI/server | บังคับ UTF-8 mode |
| `PYTHONIOENCODING` | CLI/server | stdout/stderr encoding |

---

## 9. ข้อจำกัดและความเสี่ยงของระบบปัจจุบัน

### 9.1 Dataset

- ข้อมูลมาจากบุคคลเดียวและคู่สนทนาจำนวนจำกัด จึงไม่ใช่ตัวแทนภาษาไทยทั่วไป
- time-gap 1 ชั่วโมงเป็น heuristic อาจรวมคนละหัวข้อไว้ session เดียวหรือแยกบทสนทนาที่ต่อเนื่องแต่เว้นนาน
- source-preserved split ลด temporal leakage แต่ไม่กำจัด phrase/style similarity ระหว่าง train/val
- source ขนาดเล็กกว่า 10 sessions ไม่มี validation coverage
- consecutive messages ถูก merge ด้วยช่องว่าง ทำให้ boundary ระดับข้อความย่อยหายไป
- `source` metadata อาจมีชื่อส่วนตัว แม้ไม่ถูกส่งเข้า tokenizer จึงยังต้องปกป้องไฟล์ dataset

### 9.2 Training

- train context สูงสุด 8 messages แต่ runtime ส่งสูงสุด 6 messages เป็น train/runtime context mismatch เล็กน้อย
- raw training examples ไม่มี runtime system prompt
- curated data ถูก repeat และไม่ผ่าน raw training skip filter จึงมีอิทธิพลมากกว่าจำนวน row ดิบ
- last-assistant-only ลด supervised tokens; ถ้า dataset น้อยเกินไปอาจ under-train ได้
- `eval_loss` วัด token prediction บน validation ไม่ได้วัด persona โดยตรง
- loss gap ช่วงท้ายแสดงความเสี่ยง overfitting
- `save_total_limit=10` อาจลบ checkpoint เก่าหากจำนวน checkpoint เกินขีดจำกัด

### 9.3 Runtime

- ต้องใช้ CUDA GPU; direct evaluation ปฏิเสธ CPU
- `max_new_tokens=24` และ `MAX_REPLY_CHARS=70` เหมาะกับแชทสั้น แต่อาจตัดคำตอบที่ต้องอธิบาย
- general guard ไม่ใช้ context regex จึงยังมีโอกาสเดาชื่อ/สถานที่/private status หากโมเดลสร้างข้อความที่ไม่เข้า garbage rules
- system prompt ช่วยกำกับแต่ไม่รับประกัน compliance
- เมื่อ guard reject ไม่มี general fallback; user จะเห็น generation error
- identity finalization ทำให้ identity metric สะท้อนทั้ง model และ policy
- generation lock รองรับหนึ่งคำตอบพร้อมกัน ผู้ใช้พร้อมกันหลายคนจะพบ busy error
- SSE ปัจจุบันไม่ใช่ token-level streaming จริง

### 9.4 Frontend และ Security

- localStorage ไม่เข้ารหัส
- Access key เป็น shared secret ไม่ใช่ระบบบัญชีผู้ใช้
- Public tunnel เปิดทางให้ภายนอกใช้ GPU ของเครื่องตราบใดที่ tunnel/server ยังทำงาน
- Quick tunnel URL และ access key ต้องไม่เผยแพร่ใน repository/report
- ไม่มี rate limiting และ request queue

### 9.5 Evaluation

- prompt contamination check เป็น exact match และยกเว้นข้อความสั้น
- prompt set มี 66 ข้อและผู้ประเมิน 8 คน
- A/B assignment ชุดเดียวกันสำหรับทุกคน
- agreement ระหว่างผู้ประเมินต่ำในบางมิติ
- Live chat ไม่มี baseline และไม่มี transcript ราย turn
- reply-length ratio เป็น corpus-level ไม่ใช่ paired answer metric
- auto metrics บางตัวเป็น regex heuristic และไม่แทน human judgment

---

## 10. กติกาการดูแล Single Source of Truth

เมื่อแก้ behavior ของระบบ ต้องอัปเดตเอกสารนี้ใน commit เดียวกัน โดยเฉพาะ:

1. เปลี่ยน pipeline step, schema, session gap หรือ split rule
2. เปลี่ยน training filter, context length, curated repeat หรือ label mask
3. เปลี่ยน base model, LoRA config หรือ Trainer config
4. เพิ่ม/ลบ RAG, fallback, guard หรือ identity policy
5. เปลี่ยน runtime generation parameters หรือ history length
6. เปลี่ยน evaluation prompts, rubric, metrics หรือจำนวนผู้ประเมิน
7. promote adapter หลักหรือประกาศ evaluation run ใหม่

ลำดับความน่าเชื่อถือเมื่อข้อมูลขัดกัน:

```text
โค้ดที่รันจริง
> metrics/report artifacts ของรันที่ระบุ
> PROJECT_OVERVIEW.md
> README/เอกสารสรุปอื่น
```

ก่อนแก้เอกสารให้ตรวจ [training/train.py](training/train.py), [web_app/server.py](web_app/server.py), [minime_core/topic_guard.py](minime_core/topic_guard.py), [scripts/04_clean_and_filter.py](scripts/04_clean_and_filter.py), [scripts/05_build_jsonl.py](scripts/05_build_jsonl.py), [scripts/06_split_train_val.py](scripts/06_split_train_val.py) และ evaluation report ล่าสุดเสมอ
