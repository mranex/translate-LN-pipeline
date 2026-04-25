# LN Translate Pipeline — Final Clean Version

Đây là bản “đập đi xây lại” theo chiến lược tinh gọn:

```text
1. Volume Glossary
2. Human chuẩn hoá Volume Glossary
3. Segment Glossary
4. Volume Relationship / Pronoun Canon
5. Human chuẩn hoá Volume Relationship
6. Segment Pronoun Table = inherit từ volume canon + override nếu cần
7. Segment Context ngắn
8. Dialogue Labeling trước khi dịch
9. Translate labeled source
10. Assemble
11. QA/Fix optional
```

Mục tiêu: không bắt AI tự nhớ một đống state phức tạp nữa. Con người chuẩn hoá dữ liệu quan trọng ở cấp volume; segment chỉ kế thừa và đánh dấu ngoại lệ.

---

## 1. Cài đặt

```bash
pip install -r requirements.txt
cp .env.example .env
```

Điền API key:

```bash
DEEPSEEK_API_KEY=sk-...
```

---

## 2. Input

Source volume:

```text
data/source/volume_01.json
```

Schema:

```json
[
  {"chapter": 1, "name": "Tên chương", "content": "Nội dung tiếng Trung"}
]
```

Segment:

```text
data/segments/volume_01.segments.json
```

Schema:

```json
[
  {"chapter": 1, "name": "Tên chương", "segment": "c001_s001", "content": "Nội dung tiếng Trung của segment"}
]
```

---

## 3. Phase 1 — Glossary

Chạy extract + merge glossary:

```bash
python -m src.main glossary-prep --volumes 1
```

Hoặc từng bước:

```bash
python -m src.main extract-glossary --volume 1
python -m src.main merge-glossary --volume 1
```

Draft glossary:

```text
data/canon/glossary/drafts/volume_01.glossary.draft.json
```

Sửa file này, rồi approve:

```bash
python -m src.main approve-glossary --volume 1 --overwrite
```

---

## 4. Build Segment Glossary

```bash
python -m src.main build-segment-glossary --volume 1
```

Output:

```text
data/working/segment_glossaries/volume_01.segment_glossaries.jsonl
```

---

## 5. Phase 2 — Volume Relationship / Pronoun Canon

```bash
python -m src.main relationship-prep --volume 1
```

Hoặc từng bước:

```bash
python -m src.main extract-relationships --volume 1
python -m src.main merge-relationships --volume 1
```

Draft relationship canon:

```text
data/canon/relationships/drafts/volume_01.relationships.draft.json
```

Đây là **cấp volume**, không phải segment. Sau khi sửa:

```bash
python -m src.main approve-relationships --volume 1 --overwrite
```

---

## 6. Build Segment Pronoun Table

```bash
python -m src.main build-segment-pronouns --volume 1
```

Output:

```text
data/canon/segment_pronouns/volume_01.segment_pronouns.jsonl
```

Logic:

```text
Volume relationship canon
→ lọc theo nhân vật/segment
→ inherit rule cấp volume
→ tạo override_candidate nếu có ngoại lệ
→ báo missing_rules nếu thiếu
```

Bạn chỉ cần review ngoại lệ/missing, không phải nhập lại quan hệ nam chính/nữ chính mỗi segment.

---

## 7. Segment Context

```bash
python -m src.main build-context --volume 1
```

---

## 8. Dialogue Labeling

```bash
python -m src.main label-dialogue --volume 1
```

Output:

```text
data/working/dialogue_labels/volume_01.dialogue_labels.jsonl
```

Ví dụ:

```text
[NARRATION]: 城下，战姬静静地望着远方。
[Elen -> Tigre | confidence=0.91]: 你终于来了。
[Tigre -> Elen | confidence=0.88]: 我答应过你。
```

Review các dòng:

```text
review_required = true
speaker/listener UNKNOWN
confidence < 0.72
missing pronoun rule
```

---

## 9. Translation

```bash
python -m src.main translate --volume 1
```

---

## 10. Assemble

```bash
python -m src.main assemble --volume 1
```

Output:

```text
data/release/volume_01.vi.json
data/release/volume_01.vi.md
```

---

## 11. Full Translation Flow Sau Khi Đã Approve Glossary + Relationship

```bash
python -m src.main run-translation --volume 1
```

Lệnh này chạy:

```text
build-segment-glossary
build-segment-pronouns
build-context
label-dialogue
translate
assemble
```

---

## 12. QA/Fix Optional

Chỉ chạy khi bạn muốn:

```bash
python -m src.main qa --volume 1
python -m src.main fix --volume 1
python -m src.main assemble --volume 1 --fixed
```

---

## 13. Resume / Overwrite

Mặc định:

```json
"resume": true,
"overwrite_existing": false
```

Nếu bị lỗi API, chạy lại cùng lệnh. Item đã thành công sẽ skip.

Muốn chạy lại một step:

```bash
rm data/working/dialogue_labels/volume_01.dialogue_labels.jsonl
python -m src.main label-dialogue --volume 1
```

---

## 14. Workflow khuyến nghị

```bash
python -m src.main glossary-prep --volumes 1
# sửa data/canon/glossary/drafts/volume_01.glossary.draft.json
python -m src.main approve-glossary --volume 1 --overwrite

python -m src.main build-segment-glossary --volume 1

python -m src.main relationship-prep --volume 1
# sửa data/canon/relationships/drafts/volume_01.relationships.draft.json
python -m src.main approve-relationships --volume 1 --overwrite

python -m src.main build-segment-pronouns --volume 1
# review ngoại lệ/missing nếu có

python -m src.main build-context --volume 1
python -m src.main label-dialogue --volume 1
# review low-confidence labels nếu có

python -m src.main translate --volume 1
python -m src.main assemble --volume 1
```

Sau khi approve glossary + relationship, có thể dùng:

```bash
python -m src.main run-translation --volume 1
```

---

## 15. Tư tưởng cốt lõi

```text
Glossary = từ đúng.
Volume relationship canon = xưng hô mặc định đúng.
Segment pronoun table = inherit + override.
Dialogue labeling = biết ai nói với ai trước khi dịch.
Translation = không còn tự đoán sân khấu.
QA/Fix = chỉ chạy khi cần.
```
# translate-LN-pipeline
