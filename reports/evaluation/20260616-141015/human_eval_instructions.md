# Human Evaluation Instructions

## ไฟล์ที่ต้องใช้

- เปิด `human_eval_blind.csv` เพื่อให้คะแนน
- เปิด `human_eval_rubric.txt` เพื่อดูเกณฑ์คะแนน 1-5
- ห้ามเปิดหรือส่งต่อ `human_eval_mapping_private.txt` ระหว่างประเมิน เพราะไฟล์นั้นเฉลยว่า A/B คือ model ไหน

## ต้องอ่าน column ไหนบ้าง

- `prompt_id`: รหัสข้อ ใช้สำหรับอ้างอิง ไม่ต้องแก้
- `category`: หมวดของ prompt ไม่ต้องแก้
- `is_multi_turn`: ถ้าเป็น `Yes` ให้ดูบทสนทนาก่อนหน้าด้วย
- `conversation_context`: ข้อความก่อนหน้าในบทสนทนา ถ้าว่างแปลว่าเป็นคำถามเดี่ยว
- `final_user_message`: ข้อความล่าสุดของ user ที่ AI ต้องตอบ
- `response_A` และ `response_B`: คำตอบจาก AI สองตัว ให้ให้คะแนนแยกกัน

## ต้องกรอกคะแนนช่องไหน

ให้ใส่ตัวเลข 1-5 ในช่องต่อไปนี้เท่านั้น:

- `A_persona_consistency`, `A_style_similarity`, `A_relevance`
- `B_persona_consistency`, `B_style_similarity`, `B_relevance`
- ถ้า `is_multi_turn = Yes` ให้กรอก `A_context_consistency` และ `B_context_consistency` ด้วย
- ถ้า `is_multi_turn = No` ช่อง context consistency จะเป็น `N/A` อยู่แล้ว ไม่ต้องแก้
- `evaluator_notes`: ใส่หรือไม่ใส่ก็ได้ ใช้จดเหตุผลสั้น ๆ เช่น `ตอบไม่ตรง`, `ยาวไป`, `เหมือนมาก`

## วิธีให้คะแนน

- คะแนนต้องเป็นเลข 1, 2, 3, 4 หรือ 5 เท่านั้น
- 1 = แย่มาก / ไม่เหมือน / ไม่ตรงคำถาม
- 3 = พอใช้ / กึ่ง ๆ / มีบางส่วนตรง
- 5 = ดีมาก / เหมือนมาก / ตอบตรงมาก
- เป้าหมายหลักของงานนี้คือวัดว่า AI คุยเหมือนกัปปิตันไหม จึงให้ความสำคัญกับ `persona_consistency` และ `style_similarity` มากเป็นพิเศษ
- หลังเก็บคะแนนแล้ว script จะคำนวณ `Captain Similarity Score` = 45% persona + 35% style + 20% relevance
- ถ้า response เป็น `[REJECTED]` หรือว่าง ให้คะแนน 1 ทุก metric ที่ต้องกรอก
- อย่าแก้ข้อความใน column prompt, context, user message หรือ response
- หลังให้คะแนนเสร็จ ให้บันทึกเป็นไฟล์ของตัวเอง เช่น `rater1.csv`, `rater2.csv`, `rater3.csv`

## ลำดับการทำ

1. อ่าน `human_eval_rubric.txt`
2. เปิด `human_eval_blind.csv`
3. อ่าน `conversation_context` ถ้ามี
4. อ่าน `final_user_message`
5. อ่าน response ของ AI
6. ใส่คะแนน 1-5 ในช่องคะแนนที่ระบุ
7. ทำจนครบทุก row แล้วส่งไฟล์ CSV ที่กรอกคะแนนกลับมา

## หมายเหตุ

- ไม่มีคำตอบเดียวที่ถูกเสมอ ให้ให้คะแนนจากความรู้สึกว่าเหมือนกัปปิตันและเหมาะกับบทสนทนาแค่ไหน
- ให้ประเมินจากข้อความที่เห็นในไฟล์เท่านั้น ไม่ต้องเดาว่า AI ควรรู้อะไรนอกบทสนทนา
- ถ้าคำตอบสั้นมากแต่เข้ากับสไตล์กัปปิตันและตอบตรง ให้คะแนนได้สูง
- ถ้าคำตอบมีชื่อคน สถานที่ สถานะ หรือเรื่องส่วนตัวที่ user ไม่ได้บอก ให้หัก relevance/context ตามความเหมาะสม

**ไฟล์นี้สร้างด้วย seed=42 — reproducible**
