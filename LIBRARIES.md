# MiniMe Libraries, Runtime Stack & Dependency Policy

> **อัปเดตล่าสุด:** 24 มิถุนายน 2026
>
> **แหล่งข้อมูลเวอร์ชัน:** package metadata ใน `captain-env/Lib/site-packages`
>
> **Technical specification หลัก:** [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)

## 1. วัตถุประสงค์ของเอกสาร

ไฟล์นี้อธิบายไลบรารี เครื่องมือ และ compatibility assumptions ที่ MiniMe ใช้จริง โดยแยกเป็น:

- dependency ที่โปรเจกต์เรียกใช้โดยตรง
- dependency สำคัญที่ framework ใช้ภายใน
- Python standard library ที่ทำให้ data/evaluation scripts ไม่ต้องพึ่ง package เพิ่ม
- เครื่องมือภายนอกที่ไม่ได้ติดตั้งผ่าน `pip`
- กฎ train/validation split ซึ่งเป็นส่วนหนึ่งของ data methodology ไม่ใช่ library

เวอร์ชันที่ระบุใน [requirements.txt](requirements.txt) คือ **tested local snapshot** ไม่ใช่คำกล่าวว่าเป็น upstream release ใหม่ที่สุด และไม่ควร upgrade ทีละ package โดยไม่ทดสอบ Unsloth, Transformers, PyTorch และ Qwen ร่วมกัน

## 2. สถานะ Python Environment

| รายการ | สถานะ |
| --- | --- |
| Python ที่ใช้สร้าง venv | `3.11.9` |
| Virtual environment | `captain-env` |
| Platform | Windows x86-64 |
| CUDA wheel family | CUDA 12.8 (`cu128`) |
| Base model | `Qwen/Qwen3.5-9B` |
| Runtime adapter | `output/captain-lora` |

### 2.1 Environment health ณ วันที่ตรวจ

`captain-env/pyvenv.cfg` ชี้ไปที่:

```text
C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe
```

Python 3.11.9 ถูกติดตั้งกลับที่ path นี้แล้ว และ `captain-env\Scripts\python.exe` สามารถใช้งานได้ตามปกติ

ผลตรวจหลังซ่อม environment:

| รายการ | ผล |
| --- | --- |
| Python | `3.11.9` |
| `pip check` | ผ่าน: `No broken requirements found` |
| Core imports | ผ่าน: Torch, Unsloth, Transformers, Datasets, TRL, PEFT, FastAPI, Uvicorn |
| PyTorch | `2.10.0+cu128` |
| CUDA | พร้อมใช้งาน |
| GPU | `NVIDIA GeForce RTX 5070` |
| Syntax check | ผ่านทุก Python entry point หลัก |
| Training data check | ผ่าน: train 3,705 และ validation 478 assistant examples |
| Evaluation prompt check | ผ่าน: 66 prompts, ไม่มี duplicate ID หรือ verbatim contamination ตามเกณฑ์ปัจจุบัน |
| Server smoke test | Uvicorn และ `/health` ทำงาน; adapter เริ่มโหลดบน RTX 5070 แต่ยังไม่ถึง `ready` ภายในหน้าต่างทดสอบ 240 วินาที |

Unsloth รายงานว่า Flash Attention 2 ใช้งานไม่ได้และเลือก Xformers แทน โดยการ import และ CUDA check ยังผ่าน นี่เป็น fallback ที่รองรับใน environment ปัจจุบัน ไม่ใช่ blocker

### 2.2 การสร้าง environment ใหม่ในอนาคต

Windows venv เก็บ absolute path ของ base interpreter จึงไม่ควร copy `captain-env` ข้ามเครื่องหรือข้าม Python installation ถ้า path ของ Python เปลี่ยนให้สร้าง venv ใหม่ตามขั้นตอนนี้:

1. ติดตั้ง Python 3.11 x64 กลับมา
2. ย้ายหรือลบ `captain-env` เดิม เพื่อไม่ให้ packages เก่าปนกับ environment ใหม่
3. สร้าง `captain-env` ใหม่
4. ติดตั้ง [requirements.txt](requirements.txt)
5. ตรวจ CUDA และ imports ก่อน train/server

ตัวอย่างหลังติดตั้ง Python 3.11:

```powershell
py -3.11 -m venv captain-env
captain-env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

ตรวจ environment:

```powershell
captain-env\Scripts\python.exe -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
captain-env\Scripts\python.exe -m pip check
```

## 3. Dependency Policy

### 3.1 เหตุผลที่ pin เวอร์ชัน

LLM stack มี compatibility coupling หลายชั้น:

```text
Unsloth
-> Transformers / TRL / PEFT / Accelerate
-> PyTorch / CUDA / xFormers / bitsandbytes / Triton
-> tokenizer / safetensors / Hugging Face Hub
```

การ upgrade package เดียวอาจทำให้:

- chat template หรือ generation mask เปลี่ยน
- `SFTConfig`/`SFTTrainer` API เปลี่ยน
- 4-bit loading หรือ 8-bit optimizer ใช้ไม่ได้
- CUDA kernel, xFormers หรือ Triton โหลดไม่สำเร็จ
- adapter ที่เคยโหลดได้เกิด compatibility error

ดังนั้น [requirements.txt](requirements.txt) ใช้ exact pins สำหรับ critical stack และระบุ PyTorch CUDA 12.8 index โดยตรง

### 3.2 “ล่าสุด” ในโปรเจกต์นี้หมายถึงอะไร

ในเอกสารนี้ “ล่าสุด” หมายถึง:

- ตรงกับ environment ที่ใช้ train/evaluate adapter ปัจจุบัน
- ตรงกับ package metadata ที่ยังอยู่ใน `captain-env`
- ตรงกับ imports และ API ใน source code ปัจจุบัน

ไม่ได้หมายถึงการเปลี่ยนไปใช้ package release ล่าสุดบน PyPI อัตโนมัติ การ upgrade ต้องทำใน candidate environment และผ่าน test plan ในหัวข้อ 12

## 4. Data Pipeline: Python Standard Library

ขั้นตอน [scripts/01_delete_media.py](scripts/01_delete_media.py) ถึง [scripts/06_split_train_val.py](scripts/06_split_train_val.py) ใช้ Python standard library เท่านั้น

| Module | ใช้ใน | หน้าที่ |
| --- | --- | --- |
| `argparse` | scripts 02, 03; training/evaluation CLIs | command-line arguments |
| `collections.defaultdict` | script 06, evaluation analyzers | group sessions/evaluator records |
| `csv` | training/evaluation | เขียน metrics และอ่าน human/live-chat results |
| `glob` | scripts 02, 04, 05 | ค้น raw/filtered JSON files |
| `json` | pipeline, training, server, evaluation | JSON/JSONL และ SSE payloads |
| `os` | pipeline, training, server | filesystem และ environment variables |
| `pathlib.Path` | ทุกส่วนหลัก | path handling |
| `random` | script 06, human-eval preparation | deterministic shuffle/A-B assignment |
| `re` | cleaning, guard, metrics | regex cleaning และ heuristic checks |
| `shutil` | scripts 01/03, training | file operations และ candidate overwrite |
| `statistics` equivalent | evaluation | โปรเจกต์ใช้ฟังก์ชัน mean/SD ที่ implement ใน script เอง |
| `threading`/`asyncio` | server | background model loading, generation lock และ async SSE |
| `urllib.request` | runtime evaluation | เรียก server โดยไม่เพิ่ม HTTP client dependency |

## 5. Train/Validation Split Methodology

กฎ split อยู่ใน [scripts/06_split_train_val.py](scripts/06_split_train_val.py) และควรระบุในงานวิจัย เพราะมีผลต่อ composition ของ validation set

| Parameter | ค่า |
| --- | ---: |
| `VAL_RATIO` | 0.10 |
| `MIN_SESSIONS_FOR_VAL` | 10 |
| `SPLIT_SEED` | 42 |
| Split unit | session |
| Grouping key | `source` |
| Ordering | `session_start_ms` จากเก่าไปใหม่ |

### 5.1 Source-preserved chronological split

สำหรับแต่ละ source:

1. เรียง sessions ตามเวลา
2. ถ้ามีน้อยกว่า 10 sessions ให้เข้า train ทั้งหมด
3. ถ้ามีอย่างน้อย 10 sessions ให้ช่วงท้ายประมาณ 10% เข้า validation
4. จำนวน validation คำนวณด้วย `max(1, int(total * 0.10 + 0.5))`
5. shuffle เฉพาะ train ด้วย seed 42; validation คงลำดับเวลา

### 5.2 เหตุผลที่ source เล็กไม่ถูกแบ่ง

การเอา 1 session ออกจาก source ที่มีเพียง 1-2 sessions ทำให้ training signal ของ source นั้นหายไป 50-100% และ validation เพียงหนึ่งตัวอย่างไม่เสถียรพอจะเป็นตัวแทน source จึงเลือกเก็บ source เล็กไว้ใน train

ข้อแลกเปลี่ยน:

- รักษาความหลากหลายของข้อมูล train
- source ใหญ่ถูกวัดบนช่วงเวลาที่ใหม่กว่า
- source เล็กไม่มี validation coverage โดยตรง
- global train/val ratio อาจไม่เท่ากับ 90/10 พอดี

Snapshot ปัจจุบัน:

| รายการ | จำนวน |
| --- | ---: |
| Sessions ทั้งหมด | 1,707 |
| Train sessions | 1,545 |
| Validation sessions | 162 |
| Sources ทั้งหมด | 43 |
| Sources ที่มี validation | 22 |
| Sources train-only | 21 |

รายละเอียดเชิงวิธีวิจัยเพิ่มเติมอยู่ใน [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md#37-step-06-source-preserved-chronological-split)

## 6. Fine-tuning และ LLM Stack

เวอร์ชันด้านล่างตรงกับ installed metadata ปัจจุบัน

| Package | Version | ใช้ทำอะไร |
| --- | ---: | --- |
| `unsloth` | `2026.5.10` | โหลด Qwen แบบ 4-bit, ติด LoRA และ inference optimization |
| `unsloth_zoo` | `2026.5.5` | model support และ utilities ของ Unsloth |
| `transformers` | `5.5.0` | tokenizer, chat template, generation และ Trainer integration |
| `datasets` | `4.3.0` | โหลด JSONL และสร้าง Dataset/DatasetDict |
| `trl` | `0.23.0` | `SFTTrainer` และ `SFTConfig` |
| `peft` | `0.19.1` | LoRA/adapter abstractions |
| `accelerate` | `1.13.0` | device และ training runtime utilities |
| `safetensors` | `0.8.0rc0` | serialization ของ model/adapter tensors |
| `sentencepiece` | `0.2.1` | tokenizer compatibility |
| `tokenizers` | `0.22.2` | fast tokenizer backend |
| `huggingface_hub` | `1.17.0` | model/config download และ cache |
| `hf_transfer` | `0.1.9` | transfer acceleration สำหรับ Hugging Face |

Source หลัก: [training/train.py](training/train.py)

## 7. PyTorch, CUDA และ Kernel Stack

| Package | Version | ใช้ทำอะไร |
| --- | ---: | --- |
| `torch` | `2.10.0+cu128` | tensor runtime, CUDA และ training/inference |
| `torchvision` | `0.25.0+cu128` | companion package ที่ติดตั้งใน tested stack |
| `xformers` | `0.0.35` | optimized attention fallback ที่ environment ใช้งานได้ |
| `bitsandbytes` | `0.49.2` | 4-bit loading และ `adamw_8bit` |
| `triton-windows` | `3.7.0.post26` | Triton runtime สำหรับ Windows |
| `torchao` | `0.17.0` | PyTorch optimization/quantization utilities |

หมายเหตุ:

- `torch`/`torchvision` ใช้ CUDA 12.8 wheels จึงมี `--extra-index-url https://download.pytorch.org/whl/cu128` ใน requirements
- environment มี `xformers` และ runtime log เคย fallback มาใช้เมื่อ Flash Attention 2 ใช้งานไม่ได้
- โปรเจกต์ไม่ได้ pin `flash-attn` โดยตรง
- ต้องตรวจ `torch.cuda.is_available()` หลังสร้าง environment ใหม่ทุกครั้ง

## 8. Dataset Backend

| Package | Version | ใช้ทำอะไร |
| --- | ---: | --- |
| `numpy` | `2.4.4` | numerical backend ของ training/data stack |
| `pyarrow` | `24.0.0` | columnar backend สำหรับ Hugging Face Datasets |
| `fsspec` | `2025.9.0` | filesystem abstraction |

packages เหล่านี้ไม่ได้ถูก import โดย MiniMe code ทุกตัวโดยตรง แต่เป็น critical runtime dependencies ของ `datasets` และ training stack จึง pin ไว้เพื่อ reproducibility

## 9. Web Runtime

| Package | Version | ใช้ทำอะไร |
| --- | ---: | --- |
| `fastapi` | `0.122.0` | HTTP endpoints, middleware และ static mounting |
| `uvicorn` | `0.38.0` | ASGI server |
| `pydantic` | `2.13.4` | validate chat request schema |

Installed transitive packages ที่เกี่ยวข้อง:

| Package | Version | หมายเหตุ |
| --- | ---: | --- |
| `starlette` | `0.50.0` | ASGI/web layer ใต้ FastAPI |
| `Jinja2` | `3.1.6` | ติดตั้งใน environment; training chat template ใช้ Jinja syntax ผ่าน tokenizer |
| `protobuf` | `7.34.1` | serialization dependency ของ model stack |
| `psutil` | `7.2.2` | system/process utility ที่ dependency stack ใช้ |

Transitive packages ไม่ได้ pin ทุกตัวใน requirements เพื่อไม่ล็อก dependency graph เกินจำเป็น หากต้องการ archive environment แบบ exact ทุก package ให้เก็บ `pip freeze` แยกต่อ experiment หลังซ่อม venv

## 10. Evaluation Stack

Evaluation framework อยู่ใน [evaluation/](evaluation/) และ intentionally ไม่เพิ่ม SciPy/Pandas dependency

| ส่วน | Implementation |
| --- | --- |
| Prompt validation | Python `json`, sets และ exact-string checks |
| Automatic metrics | Python `math`, regex และ custom aggregations |
| Quadratic Weighted Kappa | implement ใน `analyze_human_eval.py` |
| Krippendorff's Alpha | implement ใน `analyze_human_eval.py` |
| Wilcoxon signed-rank | implement พร้อม exact sign-permutation ใน `analyze_human_eval.py` |
| Live chat aggregation | `csv`, `json`, `defaultdict`, custom mean/SD |

ไฟล์สำคัญ:

- [evaluation/check_prompts.py](evaluation/check_prompts.py)
- [evaluation/generate_responses.py](evaluation/generate_responses.py)
- [evaluation/compute_metrics.py](evaluation/compute_metrics.py)
- [evaluation/prepare_human_eval.py](evaluation/prepare_human_eval.py)
- [evaluation/analyze_human_eval.py](evaluation/analyze_human_eval.py)
- [evaluation/analyze_live_chat.py](evaluation/analyze_live_chat.py)

## 11. Frontend และ External Tools

### 11.1 Frontend

ไม่มี frontend framework หรือ npm build step

| Technology | ใช้ใน | หน้าที่ |
| --- | --- | --- |
| HTML | [web_app/static/index.html](web_app/static/index.html) | UI structure |
| CSS | [web_app/static/styles.css](web_app/static/styles.css) | Deep Pond / Goldfish Orange theme และ responsive layout |
| JavaScript | [web_app/static/app.js](web_app/static/app.js) | rooms, localStorage, health polling และ SSE parsing |
| Server-Sent Events | server + app.js | ส่ง status/error/reply/done events |

SSE ปัจจุบันส่งคำตอบที่ generate เสร็จแล้วใน `token` event หนึ่งครั้ง ไม่ใช่ token-by-token decoding

### 11.2 Cloudflare Tunnel

`cloudflared.exe` เป็น external executable ไม่ใช่ pip package ใช้โดย [scripts/run_public_tunnel.ps1](scripts/run_public_tunnel.ps1)

- ถ้ามีใน PATH จะใช้ตัวนั้น
- ถ้ามี `.tools/cloudflared.exe` จะใช้ local copy
- `-DownloadCloudflared` ดาวน์โหลด Windows AMD64 binary จาก GitHub releases

### 11.3 Node.js และ Sharp สำหรับ Research Diagram

[diagrams/render_human_eval_extended.js](diagrams/render_human_eval_extended.js) ใช้ Node.js และ `sharp` เพื่อสร้างไฟล์ SVG/PNG ของ research pipeline โดย dependency แยกจาก Python runtime:

| รายการ | เวอร์ชัน/ข้อกำหนด | หน้าที่ |
| --- | --- | --- |
| Node.js | `>=20` (เครื่องที่ตรวจใช้ `24.15.0`) | รัน diagram renderer |
| `sharp` | `0.34.5` | rasterize SVG เป็น PNG ขนาด 1,400 x 900 |
| pnpm | ใช้ lockfile ใน repository | ติดตั้ง Node dependency แบบ reproducible |

ไฟล์ที่กำหนด dependency คือ [package.json](package.json), [pnpm-lock.yaml](pnpm-lock.yaml) และ [pnpm-workspace.yaml](pnpm-workspace.yaml) ส่วน `node_modules/` และ `.pnpm-store/` ถูก ignore จาก Git

```powershell
pnpm install
pnpm run render:research-pipeline
```

## 12. Upgrade และ Verification Procedure

อย่าแก้ version pins หลายกลุ่มพร้อมกันใน environment หลัก ให้ทำ candidate environment แยกและตรวจตามลำดับ:

1. ติดตั้งจาก requirements ได้โดยไม่มี resolver error
2. `pip check` ผ่าน
3. import `torch`, `unsloth`, `transformers`, `trl`, `peft`, `fastapi`
4. CUDA พร้อมและเห็น GPU ที่ถูกต้อง
5. `training/train.py --data-check-only` ผ่าน
6. โหลด `output/captain-lora` ผ่าน server ได้
7. `/health` แสดง `status=ready`
8. generation smoke test ไม่มี CJK/garbage/encoding error
9. evaluation dry-run ผ่าน
10. ถ้าจะใช้ train จริง ให้ train candidate ใหม่ ห้าม overwrite adapter หลัก

ตัวอย่าง syntax/import checks หลัง environment ใช้งานได้:

```powershell
captain-env\Scripts\python.exe -m py_compile `
  training\train.py `
  web_app\server.py `
  minime_core\runtime_env.py `
  minime_core\text_cleaning.py `
  minime_core\topic_guard.py `
  scripts\04_clean_and_filter.py `
  scripts\05_build_jsonl.py `
  scripts\06_split_train_val.py

captain-env\Scripts\python.exe -c "import torch, unsloth, transformers, datasets, trl, peft, fastapi, uvicorn; print('imports ok')"
```

## 13. Version Snapshot

รายการ critical pins ที่ควรตรงกับ [requirements.txt](requirements.txt):

```text
Python             3.11.9
Unsloth            2026.5.10
Unsloth Zoo        2026.5.5
Transformers       5.5.0
Datasets           4.3.0
TRL                0.23.0
PEFT               0.19.1
Accelerate         1.13.0
PyTorch            2.10.0+cu128
Torchvision        0.25.0+cu128
xFormers           0.0.35
bitsandbytes       0.49.2
Triton Windows     3.7.0.post26
FastAPI            0.122.0
Uvicorn            0.38.0
Pydantic           2.13.4
Node.js            >=20 (tested 24.15.0)
Sharp              0.34.5
```

เมื่อมีการ train adapter หลักใหม่ ควรเก็บ requirements snapshot และ training metrics ของรอบนั้นไว้คู่กัน เพื่อให้ผลการวิจัยสามารถย้อนตรวจ environment ได้
