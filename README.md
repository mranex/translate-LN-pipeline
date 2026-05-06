# Translate LN Pipeline

Pipeline Python hỗ trợ dịch Light Novel từ tiếng Trung sang tiếng Việt bằng chuỗi prompt có output JSON cố định.

Repo hiện có ba entry point chính:

* `manual_prompt_studio.py`: GUI Tkinter để tạo prompt thủ công, copy sang chat model, paste JSON response về app và lưu artifact.
* `python -m src.main ...`: CLI/API pipeline dùng OpenAI-compatible client.
* `release_builder.py`: GUI Tkinter để ghép bản dịch theo segment thành JSON, HTML và EPUB.

README này chỉ mô tả hiện trạng repo và schema đang có trong `prompts/*.txt`.

---

## 1. Cấu trúc repo

```text
translate-LN-pipeline/
├─ config/
│  └─ config.json
├─ prompts/
│  ├─ 00_json_output_policy.txt
│  ├─ 01_extract_volume_glossary.txt
│  ├─ 02_merge_volume_glossary.txt
│  ├─ 03_build_segment_glossary.txt
│  ├─ 04_extract_volume_relationships.txt
│  ├─ 05_merge_volume_relationships.txt
│  ├─ 06_build_segment_pronouns.txt
│  ├─ 07_build_segment_context.txt
│  ├─ 08_label_dialogue.txt
│  ├─ 09_translate_labeled_segment.txt
│  ├─ 10_qa_segment.txt
│  ├─ 11_fix_segment.txt
│  └─ 12_quick_fix.txt
├─ src/
│  ├─ api_client.py
│  ├─ config_loader.py
│  ├─ json_utils.py
│  ├─ main.py
│  ├─ pipeline.py
│  ├─ prompt_loader.py
│  └─ storage.py
├─ manual_prompt_studio.py
├─ release_builder.py
├─ run.py
├─ requirements.txt
└─ README.md
```

---

## 2. Cài đặt

Tạo virtual environment:

```bash
python -m venv .venv
```

Cài dependencies trong `requirements.txt`:

```bash
pip install -r requirements.txt
```

`requirements.txt` hiện có:

```text
openai>=1.0.0
python-dotenv>=1.0.0
```

Nếu dùng `release_builder.py` để đóng EPUB, cần cài thêm `ebooklib` vì file này import `ebooklib.epub`:

```bash
pip install ebooklib
```

Tạo `.env` theo `.env.example`:

```env
DEEPSEEK_API_KEY=sk-...
```

---

## 3. Config

File config mặc định:

```text
config/config.json
```

Nội dung hiện tại:

```json
{
  "project": {
    "name": "ln_translate_pipeline_final",
    "source_language": "zh",
    "target_language": "vi"
  },
  "api": {
    "provider": "deepseek",
    "base_url": "https://api.deepseek.com",
    "api_key_env": "DEEPSEEK_API_KEY",
    "timeout_seconds": 900,
    "max_retries": 5,
    "retry_backoff_seconds": 3
  },
  "model": {
    "name": "deepseek-reasoner",
    "temperature": null,
    "top_p": null,
    "json_mode": true
  },
  "runtime": {
    "max_workers": 30,
    "resume": true,
    "overwrite_existing": false
  },
  "dialogue_labeling": {
    "review_confidence_threshold": 0.72,
    "auto_accept_confidence_threshold": 0.82,
    "force_review_if_unknown_speaker": true,
    "force_review_if_unknown_listener": true,
    "force_review_if_multiple_possible_speakers": true,
    "force_review_if_no_matching_pronoun_rule": true
  },
  "translation": {
    "qa_enabled_by_default": false,
    "context_strategy": "independent"
  },
  "paths": {
    "source_dir": "data/source",
    "segments_dir": "data/segments",
    "canon_dir": "data/canon",
    "working_dir": "data/working",
    "release_dir": "data/release",
    "prompts_dir": "prompts"
  }
}
```

Ghi chú theo code hiện tại:

* API key được đọc từ biến môi trường có tên trong `api.api_key_env`.
* API client dùng `OpenAI(api_key=..., base_url=...)`.
* Nếu `model.json_mode` là `true`, request dùng `response_format` với type `json_object`.
* `runtime.overwrite_existing=false` khiến batch step bỏ qua item đã có dòng JSONL thành công.
* Các prompt có placeholder `{{genre}}`. `manual_prompt_studio.py` có thay placeholder này bằng `genre` trong `project_config.json`. CLI trong `src/pipeline.py` hiện chỉ truyền `INPUT_JSON` vào prompt.

---

## 4. Input data

### 4.1. Source volume

Theo `src/storage.py`, source volume được đọc từ:

```text
data/source/volume_01.json
```

Schema dạng list:

```json
[
  {
    "chapter": 1,
    "name": "Tên chương",
    "content": "Nội dung tiếng Trung"
  }
]
```

Schema dạng object có key `chapters`:

```json
{
  "chapters": [
    {
      "chapter": 1,
      "name": "Tên chương",
      "content": "Nội dung tiếng Trung"
    }
  ]
}
```

### 4.2. Segment file

Theo `src/storage.py`, segment file được đọc từ:

```text
data/segments/volume_01.segments.json
```

Schema dạng list:

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

Schema dạng object có key `segments`:

```json
{
  "segments": [
    {
      "chapter": 1,
      "name": "Tên chương",
      "segment": "c001_s001",
      "content": "Nội dung tiếng Trung của segment"
    }
  ]
}
```

`src/json_utils.py` dùng `segment` làm `item_id` nếu record có field này. Nếu không có `segment`, `item_id` fallback thành dạng `c001`, `c002`, ... dựa trên `chapter`.

---

## 5. JSON output policy

File:

```text
prompts/00_json_output_policy.txt
```

Nội dung:

```text
Return strict JSON only. Do not include markdown. Do not wrap JSON in code fences. Do not include comments. Use null when unknown. Use [] for empty arrays. Confidence must be a number from 0 to 1.
```

`src/prompt_loader.py` thay `{{JSON_OUTPUT_POLICY}}` trong từng prompt bằng nội dung file này.

`src/json_utils.py` có `loads_json_maybe()` để parse JSON. Hàm này xử lý được response bị bọc trong code fence, hoặc cố lấy object từ dấu `{` đầu tiên đến dấu `}` cuối cùng nếu parse trực tiếp thất bại.

---

## 6. CLI commands

Entry point:

```bash
python -m src.main <command>
```

Các command hiện có:

```bash
python -m src.main glossary-prep --volumes 1
python -m src.main glossary-prep --volumes 1-5
python -m src.main glossary-prep --volumes 1,3,7-10
python -m src.main glossary-prep --volumes all

python -m src.main extract-glossary --volume 1
python -m src.main merge-glossary --volume 1
python -m src.main merge-glossary --volume 1 --no-previous
python -m src.main approve-glossary --volume 1
python -m src.main approve-glossary --volume 1 --overwrite
python -m src.main approve-glossary --volume 1 --from-file path/to/file.json --overwrite

python -m src.main relationship-prep --volume 1
python -m src.main extract-relationships --volume 1
python -m src.main merge-relationships --volume 1
python -m src.main merge-relationships --volume 1 --no-previous
python -m src.main approve-relationships --volume 1
python -m src.main approve-relationships --volume 1 --overwrite
python -m src.main approve-relationships --volume 1 --from-file path/to/file.json --overwrite

python -m src.main build-segment-glossary --volume 1
python -m src.main build-segment-pronouns --volume 1
python -m src.main build-context --volume 1
python -m src.main label-dialogue --volume 1
python -m src.main translate --volume 1
python -m src.main assemble --volume 1

python -m src.main qa --volume 1
python -m src.main fix --volume 1
python -m src.main assemble --volume 1 --fixed

python -m src.main run-translation --volume 1
```

Shortcut trong `src/pipeline.py`:

* `glossary-prep`: chạy `extract_glossary` rồi `merge_glossary`.
* `relationship-prep`: chạy `extract_relationships` rồi `merge_relationships`.
* `run-translation`: chạy `build_segment_glossary`, `build_segment_pronouns`, `build_segment_context`, `label_dialogue`, `translate`, rồi `assemble`.

---

## 7. JSONL wrapper

Các batch step trong `src/pipeline.py` ghi JSONL theo wrapper này khi thành công:

```json
{
  "item_id": "c001_s001",
  "status": "success",
  "result": {}
}
```

Khi lỗi:

```json
{
  "item_id": "c001_s001",
  "status": "failed",
  "error": "Error message"
}
```

Nếu `runtime.overwrite_existing=false`, item đã có dòng `status="success"` sẽ bị skip khi chạy lại cùng output path.

---

## 8. Prompt schemas

Phần này chép lại schema output đang được khai báo trong `prompts/*.txt`.

### 8.1. `01_extract_volume_glossary.txt`

Task: extract translation-relevant glossary candidates từ một chapter hoặc segment. Prompt yêu cầu không dịch chapter, không tóm tắt plot, chỉ extract term quan trọng cho dịch về sau.

Scope trong prompt:

* Character names
* Aliases, titles, epithets, nicknames
* Locations
* Organizations
* Weapons, artifacts
* Magic, skills, techniques, named attacks
* Important recurring concepts

Output:

```json
{
  "item_id": "",
  "chapter": 0,
  "segment": null,
  "candidates": [
    {
      "source": "",
      "suggested_vi": "",
      "type": "character|alias|title|epithet|location|organization|weapon|artifact|magic|skill|technique|named_attack|concept|other",
      "reason": ""
    }
  ],
  "uncertain_items": []
}
```

CLI output:

```text
data/working/glossary_extractions/volume_01.glossary_extractions.jsonl
```

### 8.2. `02_merge_volume_glossary.txt`

Task: merge chapter-level extraction outputs thành volume-level glossary và character merge candidates. Prompt yêu cầu không dịch novel, không merge directed relationship/pronoun data, không overwrite existing canon.

Status rules trong prompt:

* `confirmed`: strict hard-translate. Translation model sẽ force exact term.
* `tentative`: soft-translate. Translation model dùng như reference nhưng có thể adapt theo context.

Output:

```json
{
  "volume": 0,
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

CLI outputs:

```text
data/canon/glossary/drafts/volume_01.glossary.draft.json
data/canon/glossary/finalized/volume_01.glossary.json
```

### 8.3. `03_build_segment_glossary.txt`

Task: filter `volume_glossary` xuống các item xuất hiện hoặc trực tiếp liên quan tới segment hiện tại. Prompt yêu cầu không dịch segment, không invent glossary item mới, và đưa term quan trọng còn thiếu vào `missing_glossary_candidates`.

Output:

```json
{
  "item_id": "",
  "chapter": 0,
  "segment": "",
  "segment_glossary": [
    {
      "id": "",
      "source": "",
      "vi": "",
      "type": "",
      "aliases": [],
      "status": "confirmed|tentative",
      "notes": ""
    }
  ],
  "missing_glossary_candidates": [
    {
      "source": "",
      "suggested_vi": "",
      "reason": ""
    }
  ]
}
```

CLI output:

```text
data/working/segment_glossaries/volume_01.segment_glossaries.jsonl
```

### 8.4. `04_extract_volume_relationships.txt`

Task: extract volume-level relationship/pronoun candidates. Prompt yêu cầu giữ đơn giản, không tạo emotional states phức tạp. Directed pair quan trọng: `A -> B` khác `B -> A`. Prompt cũng yêu cầu extract self-reference pairs với `listener` là `self` khi có.

Output:

```json
{
  "item_id": "",
  "chapter": 0,
  "segment": null,
  "relationship_candidates": [
    {
      "speaker": "",
      "listener": "",
      "speaker_is_to_listener": "",
      "listener_is_to_speaker": "",
      "self": "",
      "other": "",
      "relationship": ""
    }
  ],
  "uncertain_pairs": []
}
```

CLI output:

```text
data/working/relationship_extractions/volume_01.relationships_extractions.jsonl
```

### 8.5. `05_merge_volume_relationships.txt`

Task: merge chapter-level extraction outputs thành volume-level relationship merge candidates. Prompt yêu cầu giữ đơn giản với `speaker`, `listener`, `relationship`, `self`, `other`, `notes`; không dịch novel; không discard variants; không overwrite existing canon; không tạo state machine phức tạp.

Status rules trong prompt:

* `confirmed`: relationship giữa hai nhân vật đã confirmed.
* `tentative`: relationship soft/uncertain và có thể đổi.

Output:

```json
{
  "volume": 0,
  "relationship_pronoun_canon": [
    {
      "id": "",
      "speaker": "",
      "listener": "",
      "relationship": "",
      "self": "",
      "other": "",
      "scope": "volume_default",
      "status": "confirmed|tentative",
      "variants": [
        {
          "self": "",
          "other": "",
          "relationship": ""
        }
      ],
      "notes": ""
    }
  ],
  "review_notes": []
}
```

CLI outputs:

```text
data/canon/relationships/drafts/volume_01.relationships.draft.json
data/canon/relationships/finalized/volume_01.relationships.json
```

### 8.6. `06_build_segment_pronouns.txt`

Task: build segment-level pronoun table bằng cách inherit từ finalized volume relationship/pronoun canon. Prompt yêu cầu chỉ tạo `segment_override_candidates` khi source rõ ràng cho thấy local change, và mark `missing_rules` nếu dialogue pair xuất hiện nhưng không có volume rule.

Output:

```json
{
  "item_id": "",
  "chapter": 0,
  "segment": "",
  "segment_pronoun_table": [
    {
      "speaker": "",
      "listener": "",
      "relationship": "",
      "self": "",
      "other": "",
      "variants": [
        {
          "self": "",
          "other": "",
          "relationship": ""
        }
      ],
      "source": "inherited_from_volume|segment_override|fallback",
      "notes": ""
    }
  ],
  "segment_override_candidates": [
    {
      "speaker": "",
      "listener": "",
      "self": "",
      "other": "",
      "reason": ""
    }
  ],
  "missing_rules": [
    {
      "speaker": "",
      "listener": "",
      "reason": ""
    }
  ]
}
```

CLI output:

```text
data/canon/segment_pronouns/volume_01.segment_pronouns.jsonl
```

### 8.7. `07_build_segment_context.txt`

Task: create short translation-useful context cho một segment. Prompt yêu cầu không tạo summary dài, không thêm analysis không phục vụ dịch, và dùng segment glossary cùng segment pronoun table.

Output:

```json
{
  "item_id": "",
  "chapter": 0,
  "segment": "",
  "context": {
    "appearing_characters": [],
    "scene_summary": "",
    "scene_type": "battlefield|private_conversation|court|travel|daily_life|action|comedy|inner_monologue|strategy|other",
    "tone": "",
    "translation_notes": []
  }
}
```

CLI output:

```text
data/working/segment_contexts/volume_01.segment_contexts.jsonl
```

### 8.8. `08_label_dialogue.txt`

Task: label only dialogue lines trong source segment bằng speaker/listener tags. Prompt yêu cầu không dịch, không rewrite source text, không add/remove content, không label narration, không tạo `[NARRATION]` tags. `labeled_source` phải preserve full original segment content, nhưng chỉ dialogue lines nhận label.

Label examples trong prompt:

```text
[Tigre -> self]: source dialogue
[Tigre -> Elen]: source dialogue
[Elen -> GROUP]: source dialogue
[UNKNOWN -> UNKNOWN]: source dialogue
```

Output schema thực tế trong prompt:

```json
{
  "item_id": "",
  "chapter": 0,
  "segment": "",
  "labeled_source": ""
}
```

Lưu ý: phần rule của prompt có câu `units should contain dialogue units only`, nhưng output schema hiện không khai báo field `units`.

CLI output:

```text
data/working/dialogue_labels/volume_01.dialogue_labels.jsonl
```

### 8.9. `09_translate_labeled_segment.txt`

Task: translate labeled source sang tiếng Việt. Prompt nói full source content nằm trong `dialogue_labels.labeled_source` và cần dùng field đó làm source để dịch.

Các rule chính trong prompt:

* Plain unlabeled source text là narration.
* Dialogue lines được label dạng `[Speaker -> Listener | confidence=...]: source dialogue`.
* Dùng labels để chọn xưng hô tiếng Việt.
* Không output speaker labels trong final translation.
* Không translate labels.
* Không remove quotation marks hoặc dialogue boundary markers.
* Không merge dialogue vào narration.
* Nếu glossary term có `status="confirmed"`, phải dùng exact translation.
* Nếu glossary term có `status="tentative"`, xem là strong suggestion nhưng có thể adapt theo context.
* Apply `segment_pronoun_table` theo `speaker -> listener`.
* Không invent pronoun pairs.
* Không dùng variants trừ khi được liệt kê rõ.
* Nếu speaker/listener là `UNKNOWN`, dịch trung tính và tránh risky pronouns như `anh/em`.
* Không override dialogue labels bằng guess riêng trừ khi label là `UNKNOWN`.
* Unlabeled text trong `labeled_source` là narration.
* Giữ third-person references ổn định.
* Không dùng `hắn` trừ khi narration hostile, dismissive hoặc nhân vật được frame như vậy.

Output:

```json
{
  "item_id": "",
  "volume": 0,
  "chapter": 0,
  "name": "",
  "segment": "",
  "translation": "",
  "translator_notes": []
}
```

CLI output:

```text
data/working/translations/draft/volume_01.translated.jsonl
```

### 8.10. `10_qa_segment.txt`

Task: check translated segment against source segment, labeled dialogue, segment glossary, segment pronoun table và segment context. Prompt nói QA là optional và chỉ nên report meaningful errors.

Prompt check:

1. Glossary mismatch
2. Wrong pronouns according to speaker -> listener labels
3. English terms not allowed by glossary
4. Added/omitted meaning
5. Major tone mismatch

Output:

```json
{
  "item_id": "",
  "volume": 0,
  "chapter": 0,
  "segment": "",
  "requires_fix": false,
  "max_severity": "none|low|medium|high|critical",
  "issues": [
    {
      "severity": "low|medium|high|critical",
      "type": "glossary|pronoun|speaker_label|meaning|tone|other",
      "source_excerpt": "",
      "translation_excerpt": "",
      "problem": "",
      "expected": "",
      "suggested_fix": "",
      "requires_fix": false
    }
  ],
  "summary": ""
}
```

CLI output:

```text
data/working/translations/qa/volume_01.qa.jsonl
```

### 8.11. `11_fix_segment.txt`

Task: apply QA fixes to translated segment. Prompt yêu cầu không rewrite unrelated parts, không đổi glossary hoặc pronoun rules, và return full corrected segment.

Output:

```json
{
  "item_id": "",
  "volume": 0,
  "chapter": 0,
  "segment": "",
  "fixed_translation": "",
  "applied_fixes": [],
  "remaining_concerns": []
}
```

CLI output:

```text
data/working/translations/fixed/volume_01.fixed.jsonl
```

### 8.12. `12_quick_fix.txt`

Task: fix một snippet cụ thể của bản dịch theo instruction của user.

Input prompt sử dụng các field:

```json
{
  "source_context": "",
  "highlighted_translation_to_fix": "",
  "instruction": ""
}
```

Rules trong prompt:

* Chỉ translate/fix `highlighted_translation_to_fix`.
* Không rewrite entire segment.
* `new_translation_snippet` phải thay thế được snippet cũ trong câu rộng hơn mà không hỏng ngữ pháp.

Output:

```json
{
  "new_translation_snippet": "",
  "reasoning": ""
}
```

---

## 9. Workflow CLI/API đầy đủ

```bash
# 1. Glossary canon
python -m src.main extract-glossary --volume 1
python -m src.main merge-glossary --volume 1
python -m src.main approve-glossary --volume 1 --overwrite

# 2. Relationship/pronoun canon
python -m src.main extract-relationships --volume 1
python -m src.main merge-relationships --volume 1
python -m src.main approve-relationships --volume 1 --overwrite

# 3. Segment data
python -m src.main build-segment-glossary --volume 1
python -m src.main build-segment-pronouns --volume 1
python -m src.main build-context --volume 1
python -m src.main label-dialogue --volume 1

# 4. Translation
python -m src.main translate --volume 1
python -m src.main assemble --volume 1

# 5. Optional QA/Fix
python -m src.main qa --volume 1
python -m src.main fix --volume 1
python -m src.main assemble --volume 1 --fixed
```

Nếu đã có finalized glossary và finalized relationships:

```bash
python -m src.main run-translation --volume 1
```

---

## 10. Artifact paths

Với volume 1 và paths mặc định:

```text
data/working/glossary_extractions/volume_01.glossary_extractions.jsonl

data/canon/glossary/drafts/volume_01.glossary.draft.json
data/canon/glossary/finalized/volume_01.glossary.json

data/working/segment_glossaries/volume_01.segment_glossaries.jsonl

data/working/relationship_extractions/volume_01.relationships_extractions.jsonl

data/canon/relationships/drafts/volume_01.relationships.draft.json
data/canon/relationships/finalized/volume_01.relationships.json

data/canon/segment_pronouns/volume_01.segment_pronouns.jsonl

data/working/segment_contexts/volume_01.segment_contexts.jsonl

data/working/dialogue_labels/volume_01.dialogue_labels.jsonl

data/working/translations/draft/volume_01.translated.jsonl
data/working/translations/qa/volume_01.qa.jsonl
data/working/translations/fixed/volume_01.fixed.jsonl

data/release/volume_01.vi.json
data/release/volume_01.vi.md
```

---

## 11. Assemble output

`assemble` đọc translation JSONL và ghép các segment theo chapter.

Draft mode đọc:

```text
data/working/translations/draft/volume_01.translated.jsonl
```

và lấy:

```text
result.translation
```

Fixed mode đọc:

```text
data/working/translations/fixed/volume_01.fixed.jsonl
```

và ưu tiên:

```text
result.fixed_translation
```

Nếu không có `fixed_translation`, code fallback sang `result.translation`.

JSON release có dạng:

```json
{
  "volume": 1,
  "chapters": [
    {
      "chapter": 1,
      "name": "Tên chương",
      "segments": [
        {
          "segment": "c001_s001",
          "translation": ""
        }
      ],
      "content": ""
    }
  ]
}
```

Markdown release có dạng:

```text
# Volume 01

## Chapter 1 — Tên chương

Nội dung chương đã ghép
```

---

## 12. Manual Prompt Studio

Chạy:

```bash
python manual_prompt_studio.py
```

Tên app trong code:

```text
Manual Prompt Studio v2
```

Workspace path trong class `WS`:

```text
<repo_root>/data/<project_name>/
```

Các path chính:

```text
data/<project_name>/project_config.json

data/<project_name>/source/volume_01.json
data/<project_name>/segments/volume_01.segments.json

data/<project_name>/canon/glossary/drafts/volume_01.glossary.draft.json
data/<project_name>/canon/glossary/finalized/volume_01.glossary.json

data/<project_name>/canon/relationships/drafts/volume_01.relationships.draft.json
data/<project_name>/canon/relationships/finalized/volume_01.relationships.json

data/<project_name>/working/glossary_extractions/volume_01.glossary_extractions.jsonl
data/<project_name>/working/relationship_extractions/volume_01.relationships_extractions.jsonl
data/<project_name>/working/segment_glossaries/volume_01.segment_glossaries.jsonl
data/<project_name>/canon/segment_pronouns/volume_01.segment_pronouns.jsonl
data/<project_name>/working/segment_contexts/volume_01.segment_contexts.jsonl
data/<project_name>/working/dialogue_labels/volume_01.dialogue_labels.jsonl
data/<project_name>/working/translations/draft/volume_01.translated.jsonl
data/<project_name>/working/translations/qa/volume_01.qa.jsonl
data/<project_name>/working/translations/fixed/volume_01.fixed.jsonl

data/<project_name>/release/volume_01.vi.json
data/<project_name>/release/volume_01.vi.md
```

Default `project_config.json` nếu chưa có:

```json
{
  "name": "<project_name>",
  "genre": "",
  "level": "Heavy",
  "enabled_steps": []
}
```

Manual Prompt Studio render prompt bằng cách thay:

* `{{JSON_OUTPUT_POLICY}}`
* `{{INPUT_JSON}}`
* `{{genre}}`

---

## 13. Control panel `run.py`

Chạy:

```bash
python run.py
```

Tên GUI trong code:

```text
Light Novel Translation Pipeline FINAL - Control Panel
```

Các nút chính gọi CLI command:

```text
Glossary Prep
Relationship Prep
Approve Glossary
Approve Relationships
Build Segment Glossary
Build Segment Pronouns
Build Context
Label Dialogue (AI)
RUN FULL TRANSLATION FLOW
Translate
Assemble
QA Segment
Fix Segment
Assemble (Fixed)
```

Nút `MỞ EDITOR FINAL` trong `run.py` cố mở file:

```text
ln_pipeline_final_editor.py
```

File này không có trong cây file root hiện tại của repo.

`run.py` cũng đọc `progress.json` nếu file này tồn tại.

---

## 14. Release Builder

Chạy:

```bash
python release_builder.py
```

Tên app trong code:

```text
LN Release Builder
```

Release Builder đọc từ Project Folder:

```text
segments/volume_01.segments.json
working/translations/draft/volume_01.translated.jsonl
working/translations/fixed/volume_01.fixed.jsonl
```

Translation Source trong UI có ba mode:

```text
fixed_if_available
fixed_only
draft_only
```

Draft rows lấy:

```text
result.translation
```

Fixed rows lấy:

```text
result.fixed_translation
```

Nếu fixed row không có `fixed_translation`, fallback sang:

```text
result.translation
```

Output trong Output Folder:

```text
volume_01.json
volume_01_html/
  0.html
  chapter_0001.html
  chapter_0002.html
  ...
volume_01.release_manifest.json
```

Nếu bật Pack EPUB, output EPUB có dạng:

```text
<Book Title> - v01.epub
```

Nếu bật Add to Calibre, tool gọi:

```bash
calibredb add <epub_path>
```

---

## 15. Ghi chú hiện trạng

Các điểm dưới đây là mô tả code hiện tại:

* `requirements.txt` chưa liệt kê `ebooklib`, nhưng `release_builder.py` import `ebooklib.epub`.
* CLI/API pipeline trong `src/pipeline.py` hiện không truyền `genre` vào `render()`, dù prompt có placeholder `{{genre}}`.
* `prompts/08_label_dialogue.txt` có rule nhắc tới `units`, nhưng output schema chỉ có `labeled_source`.
* `run.py` có nút mở `ln_pipeline_final_editor.py`, nhưng file này không có trong cây file root hiện tại của repo.
* `config/config.json` có `dialogue_labeling` thresholds, và `label_dialogue()` truyền config này vào `INPUT_JSON`; schema output của prompt label dialogue hiện chỉ khai báo `item_id`, `chapter`, `segment`, `labeled_source`.

---

## 16. Workflow tổng quát

```text
source/volume_XX.json
  ↓
segments/volume_XX.segments.json
  ↓
extract-glossary
  ↓
merge-glossary
  ↓
approve-glossary
  ↓
build-segment-glossary
  ↓
extract-relationships
  ↓
merge-relationships
  ↓
approve-relationships
  ↓
build-segment-pronouns
  ↓
build-context
  ↓
label-dialogue
  ↓
translate
  ↓
assemble
  ↓
qa / fix / assemble --fixed nếu cần
```

Pipeline dùng JSON và JSONL để lưu artifact. Các batch step nối dữ liệu bằng `item_id`; với segment record bình thường, `item_id` chính là field `segment`, ví dụ `c001_s001`.
