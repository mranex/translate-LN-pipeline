# Light Novel CN→VI Manual Prompt Pipeline — Final Knowledge Handoff

Tài liệu này tổng hợp toàn bộ tri thức, quyết định thiết kế, workflow và các công cụ đã được hình thành trong quá trình xây dựng pipeline dịch Light Novel từ bản Trung sang tiếng Việt.

Mục tiêu của tài liệu này là để có thể **chuyển sang một phiên làm việc mới hoàn toàn** mà vẫn giữ đầy đủ bối cảnh: vì sao pipeline cũ thất bại, bản final hoạt động theo nguyên tắc nào, manual workflow dùng ra sao, và các file/tool nào đang đảm nhiệm phần nào.

---

# 1. Bối cảnh dự án

Mục tiêu là dịch một series Light Novel dài nhiều volume từ bản dịch tiếng Trung sang tiếng Việt.

Đặc điểm source:

- Source là bản Trung đã được dịch thủ công từ Nhật, chất lượng tốt.
- Bối cảnh truyện là fantasy trung cổ châu Âu.
- Tên nhân vật nên ưu tiên romanization / tên phương Tây / tên canon fandom nếu đã biết.
- Danh hiệu, biệt danh, chiêu thức, vũ khí, tổ chức, khái niệm đặc thù có thể dùng Hán-Việt.
- Cần tránh văn phong cổ trang Trung, tu tiên, kiếm hiệp, cung đấu nếu source không có.
- Bản dịch mong muốn là Light Novel tiếng Việt tự nhiên, dễ đọc, không quá hiện đại, không slang mạng.

Các vấn đề từng gặp:

- Xưng hô nhân vật loạn giữa các chương/segment.
- Narrator gọi cùng một nhân vật lúc thì “cậu ấy”, lúc “anh ấy”, lúc “ông ấy”.
- Model tự đoán speaker/listener trong thoại không có chủ ngữ.
- QA/Fix tự động không đủ mạnh hoặc sửa không triệt để.
- Pipeline tự động quá phức tạp, nhiều JSON/JSONL khiến thao tác thủ công cực hình.
- Provider mạnh nhất hiện dùng chỉ có giao diện chat, không có API/global memory.

Sau nhiều lần thử, hướng cuối cùng được chọn là:

> Không cố tự động hóa toàn bộ.  
> Dùng app để **orchestrate prompt thủ công**: app chuẩn bị prompt đúng, người paste vào model chat mạnh, paste kết quả về app, app validate/lưu/đưa dữ liệu sang bước tiếp theo.

---

# 2. Vì sao các pipeline cũ không đủ ổn

Các phiên bản cũ từng đi theo hướng:

```text
extract glossary
→ extract relationships
→ merge canon
→ build translation pack
→ build scene context
→ translate
→ QA/Fix
```

Sau đó thêm:

```text
pronoun states
scene context
narrator reference policy
fallback pronoun rules
post-fix deterministic enforcement
```

Kết quả có cải thiện, nhưng vẫn không ổn định.

## 2.1. AI được giao quá nhiều quyền suy luận

Các pipeline cũ dựa vào việc model tự hiểu:

```text
- ai đang nói?
- nói với ai?
- quan hệ đang ở trạng thái nào?
- bối cảnh cảnh này là gì?
- xưng hô nào hợp?
```

Với tiếng Việt, chỉ cần sai speaker/listener một dòng thoại là xưng hô vỡ ngay.

## 2.2. Quan hệ/xưng hô không thể chỉ xử lý ở cấp segment mơ hồ

Có những quan hệ nên là canon cấp volume:

```text
Tigre -> Elen: tôi-cô
Elen -> Tigre: ta-ngươi
```

Nếu mỗi segment lại bắt AI tự suy luận, nó sẽ dao động.

## 2.3. Speaker attribution là mấu chốt

Đột phá lớn nhất là nhận ra:

> Với tiếng Việt, trước khi dịch cần biết **ai nói câu này với ai**.

Do đó pipeline final thêm bước:

```text
Dialogue Labeling
```

Ví dụ:

```text
[Elen -> Tigre]: 你终于来了。
[Tigre -> Elen]: 我答应过你。
[Tigre -> self]:
```

Sau đó mới dịch. Nhờ vậy model dịch không còn phải tự đoán sân khấu.

## 2.4. Manual chat model mạnh tốt hơn API model trong trường hợp này

Provider chat-only >500B có:

- chất lượng dịch tốt,
- hiểu tiếng Trung tốt,
- tốc độ phản hồi nhanh,
- chấp nhận nội dung nhạy cảm hơn,
- nhưng không có API và không có global memory.

Vì vậy giải pháp hợp lý là **Manual Prompt Studio**.

---

# 3. Triết lý final

Pipeline final được xây lại theo nguyên tắc:

```text
Glossary = từ đúng.
Volume relationship/pronoun canon = xưng hô mặc định đúng.
Segment pronoun table = kế thừa từ volume canon + override nếu cần.
Dialogue labeling = biết ai nói với ai trước khi dịch.
Translation = không còn tự đoán sân khấu.
QA/Fix = optional, chỉ chạy khi người dùng muốn.
```

Cốt lõi:

- Người dùng chuẩn hóa những thứ quan trọng ở cấp volume.
- App lo việc gom dữ liệu, tạo prompt, lưu artifact.
- AI chat model làm các bước cần ngôn ngữ mạnh.
- Không để AI âm thầm tự quyết định tất cả.
- Không bắt người dùng mở JSONL thủ công để copy/paste.

---

# 4. Pipeline final — tổng quan

Pipeline cuối cùng gồm các phase sau:

```text
PHASE 1 — GLOSSARY

1. Extract Volume Glossary
2. Merge Volume Glossary
3. Human chuẩn hóa Volume Glossary
4. Build Segment Glossary


PHASE 2 — RELATIONSHIP / PRONOUN

5. Extract Volume Relationships
6. Merge Volume Relationships
7. Human chuẩn hóa Volume Relationship / Pronoun Canon
8. Build Segment Pronoun Table


PHASE 3 — SEGMENT PREP

9. Build Segment Context
10. Label Dialogue
11. Human review low-confidence dialogue labels nếu cần


PHASE 4 — TRANSLATION

12. Translate Labeled Segment
13. Assemble Volume


PHASE 5 — OPTIONAL

14. QA
15. Fix
16. Assemble Fixed Volume
```

---

# 5. Dữ liệu đầu vào

## 5.1. Source volume gốc

File source gốc nằm ở:

```text
data/source/volume_01.json
```

Schema:

```json
[
  {
    "chapter": 1,
    "name": "Tên chương",
    "content": "Nội dung tiếng Trung"
  }
]
```

## 5.2. Segment file

File segment nằm ở:

```text
data/segments/volume_01.segments.json
```

Schema:

```json
[
  {
    "chapter": 1,
    "name": "Tên chương",
    "segment": "c001_s001",
    "content": "Nội dung tiếng Trung của segment"
  }
]
```

`segment` nên ổn định, ví dụ:

```text
c001_s001
c001_s002
c002_s001
```

Đây là key quan trọng để nối artifact qua các bước.

---

# 6. Các artifact chính

Pipeline lưu dữ liệu dưới dạng file JSON/JSONL để dễ backup và inspect.

## 6.1. Glossary

Draft glossary:

```text
data/canon/glossary/drafts/volume_01.glossary.draft.json
```

Finalized glossary:

```text
data/canon/glossary/finalized/volume_01.glossary.json
```

Schema chính:

```json
{
  "volume": 1,
  "volume_merge_glossary": [
    {
      "id": "",
      "source": "",
      "vi": "",
      "type": "character|alias|title|epithet|location|organization|weapon|artifact|magic|skill|technique|named_attack|concept|other",
      "aliases": [],
      "status": "confirmed|tentative|conflict|deprecated",
      "notes": ""
    }
  ],
  "review_notes": []
}
```

## 6.2. Segment Glossary

```text
data/working/segment_glossaries/volume_01.segment_glossaries.jsonl
```

Mỗi dòng là một artifact cho một segment.

Schema chính:

```json
{
  "item_id": "c001_s001",
  "status": "success",
  "result": {
    "item_id": "c001_s001",
    "chapter": 1,
    "segment": "c001_s001",
    "segment_glossary": [
      {
        "id": "",
        "source": "",
        "vi": "",
        "type": "",
        "rule": "always_use|use_when_context_matches",
        "forbidden_translations": [],
        "notes": ""
      }
    ],
    "missing_glossary_candidates": []
  }
}
```

## 6.3. Volume Relationship / Pronoun Canon

Draft:

```text
data/canon/relationships/drafts/volume_01.relationships.draft.json
```

Finalized:

```text
data/canon/relationships/finalized/volume_01.relationships.json
```

Schema chính:

```json
{
  "volume": 1,
  "relationship_pronoun_canon": [
    {
      "id": "",
      "speaker": "Tigre",
      "listener": "Elen",
      "relationship": "đồng minh / có thiện cảm",
      "self": "tôi",
      "other": "cô",
      "scope": "volume_default",
      "status": "confirmed|tentative|conflict|deprecated",
      "variants": [
        {
          "self": "ta",
          "other": "ngươi",
          "usage": "khi giữ thế bề trên / trêu chọc",
          "confidence": 0.78
        }
      ],
      "notes": "",
      "needs_human_review": false
    }
  ],
  "review_notes": []
}
```

Điểm quan trọng:

> Relationship/pronoun canon là **cấp volume**.  
> Không nhập lại quan hệ nam chính/nữ chính cho từng segment.

## 6.4. Segment Pronoun Table

```text
data/canon/segment_pronouns/volume_01.segment_pronouns.jsonl
```

Schema chính:

```json
{
  "item_id": "c001_s001",
  "status": "success",
  "result": {
    "item_id": "c001_s001",
    "chapter": 1,
    "segment": "c001_s001",
    "segment_pronoun_table": [
      {
        "speaker": "Tigre",
        "listener": "Elen",
        "relationship": "đồng minh / có thiện cảm",
        "self": "tôi",
        "other": "cô",
        "variants": [],
        "source": "inherited_from_volume|segment_override|fallback",
        "notes": ""
      }
    ],
    "segment_override_candidates": [],
    "missing_rules": []
  }
}
```

Segment pronoun table được build từ volume canon.

Logic:

```text
Volume Relationship Canon
→ lọc nhân vật xuất hiện trong segment
→ inherit xưng hô mặc định
→ thêm override candidate nếu có ngoại lệ
→ báo missing_rules nếu thiếu
```

## 6.5. Segment Context

```text
data/working/segment_contexts/volume_01.segment_contexts.jsonl
```

Schema:

```json
{
  "item_id": "c001_s001",
  "status": "success",
  "result": {
    "item_id": "c001_s001",
    "chapter": 1,
    "segment": "c001_s001",
    "context": {
      "appearing_characters": [],
      "scene_summary": "",
      "scene_type": "battlefield|private_conversation|court|travel|daily_life|action|comedy|inner_monologue|strategy|other",
      "tone": "",
      "translation_notes": []
    }
  }
}
```

Context chỉ cần ngắn, phục vụ dịch segment, không phải summary dài.

## 6.6. Dialogue Labels

```text
data/working/dialogue_labels/volume_01.dialogue_labels.jsonl
```

Schema:

```json
{
  "item_id": "c001_s001",
  "status": "success",
  "result": {
    "item_id": "c001_s001",
    "chapter": 1,
    "segment": "c001_s001",
    "labeled_source": "",
    "units": [
      {
        "unit_id": "",
        "type": "dialogue",
        "source_text": "",
        "speaker": "Tigre",
        "listener": "Elen",
        "possible_speakers": [],
        "possible_listeners": [],
        "matching_pronoun_rule": null,
        "confidence": 0.91,
        "review_required": false,
        "reason": ""
      }
    ],
    "label_report": {
      "low_confidence_units": [],
      "unknown_units": [],
      "missing_pronoun_rule_units": [],
      "human_review_required": false
    }
  }
}
```

Sau patch cuối:

- Chỉ thoại mới có label.
- Narration giữ nguyên plain text trong `labeled_source`.
- Không dùng `[NARRATION]`.

Ví dụ đúng:

```text
城下，战姬静静地望着远方。

[Elen -> Tigre | confidence=0.91]: 你终于来了。

Tigre握紧了手中的弓。

[Tigre -> Elen | confidence=0.88]: 我答应过你。
```

## 6.7. Translation

Draft translation:

```text
data/working/translations/draft/volume_01.translated.jsonl
```

Schema:

```json
{
  "item_id": "c001_s001",
  "status": "success",
  "result": {
    "item_id": "c001_s001",
    "volume": 1,
    "chapter": 1,
    "name": "Tên chương",
    "segment": "c001_s001",
    "translation": "",
    "translator_notes": []
  }
}
```

Fixed translation optional:

```text
data/working/translations/fixed/volume_01.fixed.jsonl
```

---

# 7. Prompt design final

## 7.1. Nguyên tắc chung

Các prompt không còn cố nhồi quá nhiều global policy.

Mỗi prompt làm đúng một việc:

```text
extract glossary
merge glossary
build segment glossary
extract relationships
merge relationships
build segment pronouns
build context
label dialogue
translate
QA
fix
```

## 7.2. Điểm sửa quan trọng: translate không gửi source_content trùng lặp

Ở một thời điểm, step translate gửi cả:

```text
source_content
dialogue_labels.labeled_source
```

Điều này làm prompt phình gần gấp đôi.

Bản final nên **không gửi `source_content` trong translate input**, vì `dialogue_labels.labeled_source` đã chứa đủ source.

Translate input nên gồm:

```json
{
  "volume": 1,
  "chapter": 1,
  "segment": "c001_s001",
  "name": "Tên chương",
  "segment_glossary": {},
  "segment_pronoun_table": {},
  "segment_context": {},
  "dialogue_labels": {}
}
```

## 7.3. Narration trong prompt dịch

Sau patch cuối, prompt dịch hiểu:

```text
plain unlabeled text = narration
labeled lines = dialogue
```

Narration rules quan trọng:

```text
- Không đổi lung tung cậu ấy / anh ấy / ông ấy.
- Không đổi lung tung cô ấy / bà ấy / nàng.
- Nếu không chắc, dùng tên riêng hoặc danh hiệu canon.
- Không gọi người già là cậu ấy.
- Không gọi cô gái trẻ là bà ấy.
- Không dùng “hắn” trừ khi narration có sắc thái thù địch/khinh miệt.
```

## 7.4. Dialogue trong prompt dịch

Dialogue rules:

```text
- Dialogue labels define who speaks to whom.
- Do not output speaker labels.
- Use segment_pronoun_table by speaker -> listener.
- If UNKNOWN/GROUP, avoid risky pronouns.
- Use variants only if explicitly provided and phù hợp immediate tone.
```

---

# 8. Manual Prompt Studio

## 8.1. Vai trò

Manual Prompt Studio là app chính để vận hành workflow chat-only.

Nó không gọi API.

Nó làm các việc:

```text
- mở project workspace
- đọc source/segments/artifacts
- generate prompt hoàn chỉnh cho từng step
- copy prompt để paste vào chat model
- nhận response JSON paste ngược lại
- validate/import response
- lưu artifact
- mở editor để sửa glossary/pronoun/dialogue labels
- assemble/release local nếu cần
```

## 8.2. Vì sao cần app này

Provider model mạnh hiện dùng chỉ có chat UI, không có API.

Nếu thao tác trực tiếp bằng file JSON/JSONL sẽ rất đau:

```text
- phải tự copy source
- tự copy glossary
- tự copy pronoun table
- tự copy prompt
- tự paste result vào file
- dễ sai key/segment
```

Manual Prompt Studio biến pipeline thành thao tác:

```text
Generate Prompt
Copy
Paste to chat
Paste response
Validate
Import
Next step
```

## 8.3. Bản v1

Bản v1 có:

```text
- Dark Tkinter UI
- Project tree Volume → Chapter → Segment
- Step list theo node
- Generate/Copy prompt
- Paste response/Validate/Import
- Artifact editor cơ bản
- Review Queue cơ bản
- Local build: segment glossary / segment pronouns / assemble
```

## 8.4. Bản v2

Bản v2 nâng cấp:

```text
- build segment glossary chuyển thành prompt-first
- build segment pronouns chuyển thành prompt-first
- thêm editor chuyên cho workflow mới:
  - Volume Glossary
  - Volume Relationships
  - Segment Glossaries
  - Segment Pronouns
- vẫn giữ Assemble local
```

Điểm này rất quan trọng vì workflow mới muốn tận dụng model chat mạnh cho cả bước build segment glossary/pronouns, thay vì Python local đơn giản.

## 8.5. Cách dùng Manual Prompt Studio

Chạy:

```bash
python manual_prompt_studio_v2.py
```

Hoặc mở project root:

```bash
python manual_prompt_studio_v2.py /path/to/project_root
```

Quy trình cơ bản:

1. Chọn volume/chapter/segment trong tree.
2. Chọn step cần làm.
3. Bấm `Generate Prompt`.
4. Bấm `Copy Prompt`.
5. Paste vào chat model.
6. Copy response JSON từ chat.
7. Paste vào app.
8. Validate.
9. Import.
10. Chuyển sang step tiếp theo.

---

# 9. Editor cho workflow mới

Có một editor riêng theo kiểu bảng trái + JSON chi tiết phải.

Các tab quan trọng:

```text
Volume Glossary
Volume Relationships
Segment Glossaries
Segment Pronouns
Segment Contexts
Dialogue Labels
Reference
```

Mục đích:

- Không phải mở hàng ngàn dòng JSON bằng Notepad.
- Có thể lọc/search item.
- Có thể sửa từng record.
- Có thể validate lỗi cơ bản:
  - glossary thiếu source/vi
  - relationship thiếu speaker/listener/self/other
  - segment_pronouns có missing_rules
  - dialogue_labels cần review

Editor được thiết kế dựa trên file editor đã tải lên và dùng cùng kiểu dark Tkinter.

---

# 10. Release Builder

## 10.1. Mục tiêu

Tool `ln_release_builder.py` dùng để:

1. Đọc workspace pipeline.
2. Ghép translation JSONL theo segment.
3. Tái tạo JSON 3 biến:

```json
[
  {
    "chapter": 1,
    "name": "Tên chương",
    "content": "Nội dung chương đã ghép"
  }
]
```

4. Tạo thư mục HTML chương.
5. Tạo `0.html` TOC.
6. Sẵn sàng để nén vào EPUB workflow.

Tool này kế thừa style HTML/TOC từ script JSON-to-HTML đã tải lên, nhưng thêm bước đọc trực tiếp từ workspace pipeline.

## 10.2. Cách chạy

```bash
python ln_release_builder.py
```

Chọn:

```text
Project Root
Output Folder
Volume
Translation Source:
  fixed_if_available
  fixed_only
  draft_only
Novel Title
```

## 10.3. Output

Ví dụ với volume 1:

```text
volume_01.json
volume_01_html/
  0.html
  chapter_0001.html
  chapter_0002.html
  ...
volume_01.release_manifest.json
```

## 10.4. JSON output

```json
[
  {
    "chapter": 1,
    "name": "Tên chương",
    "content": "Nội dung ghép từ các segment"
  }
]
```

## 10.5. HTML output

Mỗi chương:

```text
chapter_0001.html
chapter_0002.html
...
```

TOC:

```text
0.html
```

HTML dùng class tương thích workflow cũ:

```html
<body class="calibre">
<h1 class="header">...</h1>
<p class="calibre3">...</p>
```

Có tùy chọn copy:

```text
0001.css
0002.css
```

---

# 11. Workflow khuyến nghị hiện tại

## 11.1. Chuẩn bị volume

Đảm bảo có:

```text
data/source/volume_01.json
data/segments/volume_01.segments.json
```

## 11.2. Glossary

Trong Manual Prompt Studio:

```text
Volume/Chapter → Extract Glossary
Volume → Merge Glossary
Canon Studio → sửa Volume Glossary
Approve/Save Finalized Glossary
```

Hoặc file:

```text
data/canon/glossary/finalized/volume_01.glossary.json
```

## 11.3. Segment Glossary

```text
Segment → Build Segment Glossary
Paste model result
Import
Review if missing_glossary_candidates not empty
```

## 11.4. Relationship / Pronoun

```text
Volume/Segment → Extract Relationships
Volume → Merge Relationships
Canon Studio → sửa Volume Relationship Canon
Approve/Save Finalized Relationships
```

File:

```text
data/canon/relationships/finalized/volume_01.relationships.json
```

## 11.5. Segment Pronouns

```text
Segment → Build Segment Pronouns
Paste model result
Import
Review:
  - segment_override_candidates
  - missing_rules
```

## 11.6. Context

```text
Segment → Build Segment Context
Paste/import
```

## 11.7. Dialogue Labeling

```text
Segment → Label Dialogue
Paste/import
Review low-confidence/UNKNOWN/missing rule
```

Sau patch cuối:

- Chỉ thoại có label.
- Narration plain text.

## 11.8. Translation

```text
Segment → Translate
Paste/import
```

Input gồm:

```text
dialogue_labels.labeled_source
segment_glossary
segment_pronoun_table
segment_context
metadata
```

Không nên gửi thêm `source_content` nếu đã có labeled_source.

## 11.9. Release

Chạy:

```bash
python ln_release_builder.py
```

Build:

```text
volume_01.json
volume_01_html/
```

---

# 12. Review policy

## 12.1. Segment Glossary cần review khi

```text
missing_glossary_candidates không rỗng
term quan trọng chưa có trong volume glossary
model đề xuất variant lạ
```

## 12.2. Segment Pronoun cần review khi

```text
segment_override_candidates không rỗng
missing_rules không rỗng
speaker/listener quan trọng không có rule
```

## 12.3. Dialogue Labels cần review khi

```text
confidence < 0.72
speaker = UNKNOWN
listener = UNKNOWN
possible_speakers nhiều hơn 1
missing_pronoun_rule_units không rỗng
```

Confidence threshold hiện được chốt quanh:

```text
review_confidence_threshold = 0.72
auto_accept_confidence_threshold = 0.82
```

Lý do:

- Nếu threshold quá thấp, bỏ sót nhiều dòng mơ hồ.
- Model thường “sợ sai” và hay cho confidence 0.5–0.6.
- Nên bắt review vùng trung bình.

---

# 13. Những quyết định quan trọng đã chốt

## 13.1. Không dùng global memory của model

Provider chat không có global memory. Tất cả context cần thiết phải nằm trong prompt.

## 13.2. Không cố auto toàn bộ

Workflow final là manual orchestration, không phải fully automated pipeline.

## 13.3. Relationship canon là cấp volume

Không nhập lại quan hệ cho từng segment.

## 13.4. Segment pronoun là inherit + override

Segment chỉ chứa rule đang dùng và ngoại lệ.

## 13.5. Dialogue labeling là bước bắt buộc trước dịch

Đây là lý do chính giúp xưng hô không còn loạn.

## 13.6. Narration không cần label

Chỉ dialogue cần speaker/listener label.

## 13.7. QA/Fix optional

Nếu bản dịch đã tốt, không cần chạy QA/Fix.  
QA/Fix có thể dùng khi nghi ngờ lỗi hoặc muốn rà batch.

## 13.8. Assemble local

Ghép file và tạo HTML nên làm bằng Python, không cần AI.

---

# 14. Các prompt quan trọng

Tên prompt theo pipeline final:

```text
01_extract_volume_glossary.txt
02_merge_volume_glossary.txt
03_build_segment_glossary.txt
04_extract_volume_relationships.txt
05_merge_volume_relationships.txt
06_build_segment_pronouns.txt
07_build_segment_context.txt
08_label_dialogue.txt
09_translate_labeled_segment.txt
10_qa_segment.txt
11_fix_segment.txt
```

Sau patch cuối, cần chú ý nhất:

## 14.1. `08_label_dialogue.txt`

Phải có luật:

```text
Label ONLY dialogue lines.
Do NOT label narration.
Do NOT create [NARRATION] tags.
labeled_source must preserve full segment content.
Narration remains plain source text.
units should contain dialogue units only.
```

## 14.2. `09_translate_labeled_segment.txt`

Phải có luật:

```text
Plain unlabeled text = narration.
Labeled lines = dialogue.
Do NOT output labels.
Use labels only to choose pronouns.
Use segment_glossary exactly.
Use segment_pronoun_table by speaker -> listener.
Narration must keep stable third-person reference.
```

---

# 15. Những lỗi đã từng gặp và cách tránh

## 15.1. Prompt translate bị phình gấp đôi

Lỗi:

```text
gửi cả source_content và dialogue_labels.labeled_source
```

Cách tránh:

```text
translate chỉ gửi dialogue_labels.labeled_source
```

## 15.2. Narration bị gắn `[NARRATION]`

Lỗi không nghiêm trọng nhưng tốn token và rối.

Cách tránh:

```text
label only dialogue
narration plain text
```

## 15.3. Model xóa dấu thoại

Cần prompt dịch nhắc:

```text
Preserve dialogue punctuation and paragraph boundaries.
Do not merge dialogue into narration.
```

## 15.4. Xưng hô quá cứng

Có thể thêm `variants` vào relationship/pronoun rule:

```json
{
  "self": "ta",
  "other": "ngươi",
  "variants": [
    {
      "self": "tôi",
      "other": "cậu",
      "usage": "khi câu thoại mềm hơn / riêng tư hơn",
      "confidence": 0.78
    }
  ]
}
```

Prompt dịch cần nói:

```text
Use primary pair as default.
Variants may be used only when listed and local tone supports it.
Do not randomly switch variants.
```

## 15.5. QA pass chung chung

Nếu cần cải thiện QA, bắt QA trả checklist:

```json
{
  "glossary_checked_count": 0,
  "pronoun_rules_checked_count": 0,
  "dialogue_units_checked_count": 0,
  "suspicious_terms_found": []
}
```

Hiện tại QA là optional nên chưa cần ưu tiên.

---

# 16. Các app/tool hiện có

## 16.1. Manual Prompt Studio v2

Chức năng:

```text
- generate prompt
- copy prompt
- paste response
- validate/import
- edit artifacts
- quản lý workflow manual
```

Chạy:

```bash
python manual_prompt_studio_v2.py
```

## 16.2. Final Editor

Chức năng:

```text
- đọc/sửa glossary/pronoun/segment artifacts
- bảng + JSON chi tiết
- validate cơ bản
```

## 16.3. Release Builder

Chức năng:

```text
- ghép translation JSONL thành JSON 3 biến
- tạo HTML chương
- tạo 0.html
- chuẩn bị folder để đóng EPUB
```

Chạy:

```bash
python ln_release_builder.py
```

---

# 17. Kết quả test hiện tại

Theo test thực tế:

- Model chat provider mạnh hoàn thành merge volume rất nhanh.
- Bản dịch sau workflow mới tốt hơn nhiều so với API DeepSeek cũ.
- Narrator không còn nhầm ngôi kể.
- Nhân vật không còn loạn xưng hô kiểu anh/em lung tung.
- Bản release không còn label speaker.
- QA test 8 segment đều pass.
- Vấn đề còn lại chỉ là prompt tuning nhỏ:
  - xưng hô hơi cứng nếu không có variants,
  - model đôi lúc bỏ dấu thoại,
  - cần giữ narration plain text không label.

Chi phí test:

```text
~5 USD
~15 triệu token
```

Được đánh giá là chấp nhận được.

---

# 18. Checklist sang phiên làm việc mới

Khi mở phiên mới, cần nắm các điểm sau:

```text
1. Đây không còn là pipeline API auto.
2. Đây là manual prompt workflow dùng chat-only model.
3. App chính là Manual Prompt Studio v2.
4. Dữ liệu cốt lõi:
   - volume glossary
   - segment glossary
   - volume relationship/pronoun canon
   - segment pronoun table
   - segment context
   - dialogue labels
   - translation
5. Dialogue labeling là bước mấu chốt.
6. Translate không gửi source_content trùng với labeled_source.
7. Narration không gắn label.
8. Release Builder xuất JSON 3 biến + HTML.
```

---

# 19. Quy trình ngắn gọn nhất hiện tại

```text
1. Chuẩn bị source + segments.
2. Dùng Manual Prompt Studio:
   - Extract/Merge/Approve Glossary
   - Build Segment Glossary
   - Extract/Merge/Approve Relationships
   - Build Segment Pronouns
   - Build Context
   - Label Dialogue
   - Translate
3. Review những item flagged.
4. Dùng Release Builder:
   - xuất volume_XX.json
   - xuất volume_XX_html/
5. Đóng EPUB bằng workflow riêng.
```

---

# 20. Tư tưởng chốt

Câu chốt của toàn bộ dự án:

> Muốn dịch Light Novel tiếng Việt ổn bằng AI, không chỉ cần model mạnh.  
> Cần một **lò luyện đan** đủ tốt: dữ liệu đúng, prompt đúng, thao tác đúng, và con người giữ quyền chuẩn hóa ở các điểm quan trọng.

Pipeline final không cố thay thế hoàn toàn con người.

Nó làm tốt hơn:

```text
App chuẩn bị nguyên liệu.
Model chat mạnh luyện đan.
Người dùng kiểm đan ở điểm quan trọng.
Tool xuất bản đóng gói thành volume/HTML.
```

Đây là hướng hiện tại cho chất lượng tốt nhất.
