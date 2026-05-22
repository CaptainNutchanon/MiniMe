# MiniMe Project - รายละเอียดแผนผังโครงการ

## 📌 ภาพรวมโครงการ

**ชื่อโครงการ:** MiniMe  
**ประเทศ:** Thailand  
**ภาษา:** Thai  
**ที่มาข้อมูล:** Instagram Direct Messages  
**วัตถุประสงค์:** ประมวลผลข้อมูลการสนทนา Instagram DM พร้อมตรวจจับอารมณ์ (Emotion Detection) สำหรับการฝึกสอนโมเดล AI

---

## 📂 โครงสร้างไฟล์

```
MiniMe/
├── data/
│   ├── raw_data/              # ข้อมูลการสนทนา Instagram DM ดิบ
│   ├── filtered/              # ข้อมูลหลังทำความสะอาด (1-on-1 conversations)
│   ├── output/                # ผลลัพธ์ขั้นสุดท้าย (JSONL + train/val splits)
│
├── scripts/                   # ขั้นตอนการประมวลผล (Sequential Pipeline)
│   ├── 01_delete_media.py       # ลบไฟล์สื่อ
│   ├── 02_rename_json.py        # ทำให้ชื่อไฟล์ JSON เป็นมาตรฐาน
│   ├── 03_flatten_inbox.py      # ปรับโครงสร้างข้อมูลให้เรียบง่าย
│   ├── 04_clean_and_filter.py   # ทำความสะอาด + คัดกรอง
│   ├── 05_build_jsonl.py        # แปลงเป็น JSONL format
│   ├── 06_tag_emotions.py       # ตรวจจับอารมณ์จากอีโมจิและคำสำคัญ
│   └── 07_split_train_val.py    # แบ่งข้อมูลเป็น train/validation
│
├── captain-env/               # Python Virtual Environment
├── unsloth_compiled_cache/    # แคชของแบบจำลองฝึกสอน (Trainers)
├── requirements.txt           # Python Dependencies
└── .git/                      # Version Control
```

---

## 🔄 ขั้นตอนการประมวลผล (Processing Pipeline)

### **ขั้นตอนที่ 1: ลบไฟล์สื่อ** (`01_delete_media.py`)
- **Input:** `data/raw_data/` (ไฟล์ JSON จาก Instagram DM export)
- **Process:** ค้นหาและลบไฟล์สื่อ (รูป, วิดีโอ, ไฟล์เสียง)
- **Output:** ข้อมูลที่ไม่มีไฟล์สื่อ

### **ขั้นตอนที่ 2: ทำให้ชื่อไฟล์เป็นมาตรฐาน** (`02_rename_json.py`)
- **Input:** ไฟล์ JSON ที่มีชื่อไม่สม่ำเสมอ
- **Process:** ตั้งชื่อไฟล์ให้มีรูปแบบเดียวกัน
- **Output:** ไฟล์ JSON ที่ชื่อเป็นมาตรฐาน

### **ขั้นตอนที่ 3: ปรับโครงสร้างข้อมูล** (`03_flatten_inbox.py`)
- **Input:** ไฟล์ JSON ที่มีโครงสร้างซ้อนกัน
- **Process:** แปลงจากโครงสร้างหลายระดับเป็นรูปแบบเรียบง่าย
- **Output:** ข้อมูลที่มีโครงสร้างเป็นเชิงเส้น

### **ขั้นตอนที่ 4: ทำความสะอาดและคัดกรอง** (`04_clean_and_filter.py`)
- **Input:** ข้อมูลที่ปรับโครงสร้างแล้ว
- **Process:**
  - ✅ แก้ไขการเข้ารหัสตัวอักษรไทย (Latin1 → UTF-8)
  - ✅ ลบข้อความระบบ (attachments, calls, shared content)
  - ✅ ลบ URL ทั้งหมด
  - ✅ เก็บเฉพาะการสนทนา 1-on-1
  - ✅ ตรวจสอบความถูกต้องของข้อมูล
- **Output:** `data/filtered/` (ข้อมูลที่ทำความสะอาดแล้ว)

### **ขั้นตอนที่ 5: แปลงเป็น JSONL** (`05_build_jsonl.py`)
- **Input:** `data/filtered/`
- **Process:** แปลงจากรูปแบบ JSON เป็น JSONL (JSON Lines - หนึ่งบรรทัดต่อข้อมูล)
- **Output:** `data/output/` (ไฟล์ JSONL)

### **ขั้นตอนที่ 6: ตรวจจับอารมณ์** (`06_tag_emotions.py`)
- **Input:** ไฟล์ JSONL
- **Process:**
  - 📊 สแกนอีโมจิในแต่ละข้อความ
  - 📊 ค้นหาคำสำคัญภาษาไทยที่บ่งบอกอารมณ์
  - 📊 แท็กข้อความด้วยป้ายอารมณ์
- **Emotion Tags:** 
  - `[เศร้า]` - Sad/Disappointed
  - `[ขำ]` - Funny/Laughing
  - `[โกรธ]` - Angry/Annoyed
  - `[ดีใจ]` - Happy/Excited/Celebrating
  - `[อบอุ่น]` - Warm/Loving/Affectionate
  - `[ตกใจ]` - Shocked/Surprised
  - `[สงสัย]` - Wondering/Thinking
  - `[เบื่อ]` - Bored/Indifferent
  - `[ขอร้อง]` - Pleading/Requesting
  - `[มีความสุข]` - Happy/Smile
- **Output:** ไฟล์ JSONL ที่มีแท็กอารมณ์

### **ขั้นตอนที่ 7: แบ่งข้อมูล** (`07_split_train_val.py`)
- **Input:** ไฟล์ JSONL ที่มีแท็กอารมณ์
- **Process:** สุ่มแบ่งข้อมูลเป็น training set และ validation set
- **Output:** 
  - `data/output/train.jsonl` - ชุดข้อมูลฝึกสอน
  - `data/output/val.jsonl` - ชุดข้อมูลตรวจสอบ

---

## 🔧 เทคโนโลยีและ Dependencies

### **Python Virtual Environment**
- **Location:** `captain-env/`
- **Activation:** `captain-env/Scripts/activate` (Windows)

### **Key Libraries**
| Library | Version | Purpose |
|---------|---------|---------|
| accelerate | 1.13.0 | การฝึกสอนแบบกระจาย (Distributed Training) |
| unsloth | Latest | เร่งความเร็วการฝึกสอน LLM |
| datasets | 4.8.5 | จัดการและประมวลผลข้อมูลขนาดใหญ่ |
| diffusers | 0.38.0 | โมเดล Diffusion |
| bitsandbytes | 0.49.2 | การบีบอัด (Quantization) |
| transformers | Latest | Hugging Face Transformers |
| torch | Latest | PyTorch Deep Learning Framework |

### **Cached Trainers** (`unsloth_compiled_cache/`)
- UnslothSFTTrainer.py
- UnslothDPOTrainer.py
- UnslothORPOTrainer.py
- UnslothPPOTrainer.py
- และอื่นๆ อีก 15+ trainers

---

## 📊 Data Flow Visualization

```
📥 Raw Instagram DM Data
        ↓
01. Delete Media Files
        ↓
02. Rename JSON Files
        ↓
03. Flatten Inbox Structure
        ↓
04. Clean & Filter (1-on-1 only)
        ↓ data/filtered/
05. Build JSONL Format
        ↓
06. Tag Emotions (Emoji + Keywords)
        ↓
07. Split Train/Validation
        ↓ data/output/
✅ Final Dataset Ready for LLM Fine-tuning
```

---

## ✨ ฟีเจอร์หลัก

### **Data Cleaning (`04_clean_and_filter.py`)**
```python
SKIP_SUBSTRINGS = {
    "sent an attachment",      # ส่งไฟล์แนบ
    "ส่งไฟล์แนบ",
    "แชร์โพสต์",              # Share posts
    "แชร์สตอรี่",              # Share stories
    "started an audio call",    # เรียกเข้า
    "missed a video chat",      # หายการเรียกวิดีโอ
    # ... และอื่นๆ
}
```

### **Encoding Fixes**
- แก้ไขปัญหาการเข้ารหัส Thai text ที่บันทึกไว้ผิด (Latin1 → UTF-8)

### **URL Removal**
- ลบลิงก์ https/http และโดเมนต่างๆ (facebook.com, instagram.com, youtube.com)

### **Emotion Detection**
- แมปอีโมจิกับป้ายอารมณ์
- ค้นหาคำสำคัญภาษาไทย
- ตรวจจับอารมณ์ที่สำคัญที่สุดในข้อความ

---

## 🎯 Use Cases

1. **Fine-tuning LLM สำหรับการวิเคราะห์อารมณ์ภาษาไทย**
2. **การศึกษา Instagram User Behavior ของชาวไทย**
3. **สร้างแบบจำลอง Emotion Classification จาก Social Media**
4. **วิจัย Natural Language Processing (NLP) ของภาษาไทยในบริบท Messaging**

---

## 📋 Quick Start

```bash
# 1. Activate virtual environment
captain-env\Scripts\activate

# 2. Run the pipeline sequentially
python scripts/01_delete_media.py
python scripts/02_rename_json.py
python scripts/03_flatten_inbox.py
python scripts/04_clean_and_filter.py
python scripts/05_build_jsonl.py
python scripts/06_tag_emotions.py
python scripts/07_split_train_val.py

# 3. Use the final dataset for training
# data/output/train.jsonl
# data/output/val.jsonl
```

---

## 📝 Notes

- ✅ ข้อมูลมาจาก Instagram Direct Messages
- ✅ โครงการใช้ Unsloth สำหรับการฝึกสอน LLM ที่รวดเร็ว
- ✅ เน้นข้อมูลภาษาไทย (Thai Language Focus)
- ✅ ระบบทำความสะอาดข้อมูลที่ครบถ้วน
- ✅ Emotion tagging อัตโนมัติ
- ✅ พร้อมสำหรับการฝึกสอนโมเดล AI

---

**Generated:** May 20, 2026  
**Status:** Active Development  
**Python Version:** 3.x  
**Virtual Environment:** captain-env/
