# Translate LN Pipeline

Translate LN Pipeline is a manual-in-the-loop studio for AI-assisted light novel and web novel translation. It is built for the ugly parts of long-form translation that one-click tools usually hand-wave away: glossary drift, pronoun mistakes, relationship direction mistakes, dialogue attribution, inconsistent naming, shallow QA, and release outputs that stop being traceable the moment something goes wrong.

The current center of gravity is `manual_studio/`, a PyQt6 desktop app called **Manual Studio v3**. It does not automatically call a model for you. Instead, it builds structured JSON inputs, renders prompt templates, lets you send those prompts to your LLM however you want, then validates and imports the JSON response back into a project workspace.

That manual loop is the point. For long fiction, blind automation is how you end up with a translation that is fast, fluent, and quietly wrong for 400 pages. This repo is designed for people who would rather keep control of canon, review points, and artifacts than pretend the model is more reliable than it is.

Older Tkinter and CLI tooling still exists in the repo, but if you just cloned this project today, **Manual Studio v3 is the place to start**.

> This is not a one-click translator. It is a structured translation studio for people who want control.

## Who This Is For

- Translators and editors who care more about consistency and controllability than raw speed.
- People using LLMs for light novel or web novel translation, but worried about hallucinations, terminology drift, pronoun drift, character relationship mistakes, and long-form chaos.
- Teams or solo operators who want persistent artifacts instead of a pile of chat logs and wishful thinking.

This is **not** for people who want to drop in a raw chapter, press a magic button, and accept whatever comes back.

## Current Main App

The main interface is the PyQt6 app in `manual_studio/`.

### Navigation panel

The left-hand navigation tree is the workflow anchor:

- `Volume` selection gives you volume-scoped steps and views.
- `Chapter` selection gives you chapter-scoped extraction steps.
- `Segment` selection gives you segment-scoped prompt work, editing, translation, QA, and fixes.

That selection drives the current context across the whole app. If you switch from a volume to a segment, the available steps, editor state, progress view, and release/canon context all switch with it.

### Main tabs

- **Prompt Studio**: choose the current workflow step, generate the prompt, copy it, paste the model response back, validate it, and import it. Local actions also appear here, but some are still placeholders.
- **Editor**: edit imported artifacts directly. Volume glossary and relationships are editable. Segment glossaries, segment pronouns, dialogue labels, and translations are editable. Segment contexts and QA are currently preview-oriented and read-only.
- **Project Progress**: shows done/partial/not-started progress for the current volume, chapter, or segment based on actual artifacts on disk.
- **Series Canon**: inspect series-level glossary and relationship canon, preview active per-volume canon, and run canon sync/build actions.
- **Release Center**: preview diagnostics, choose draft or fixed translation sources, and build release JSON, HTML, and optional EPUB outputs.

## Core Workflow

The workflow registry lives in `manual_studio/core/step_registry.py`.

### Chapter-level steps

- `extract_chapter_glossary` - AI prompt step
- `extract_chapter_relationships` - AI prompt step

### Volume-level steps

- `merge_volume_glossary` - AI prompt step
- `review_volume_glossary` - local/editor step
- `initialize_series_glossary_from_volume` - local action
- `merge_volume_relationships` - AI prompt step
- `review_volume_relationships` - local/editor step
- `initialize_series_relationships_from_volume` - local action
- `build_active_volume_glossary` - local action
- `build_active_volume_relationships` - local action
- `sync_volume_glossary_to_series` - local action
- `sync_volume_relationships_to_series` - local action
- `assemble` - registered as a local step, but the practical release-building UI today is the **Release Center** tab

### Segment-level steps

- `build_segment_glossary` - AI prompt step
- `build_segment_glossary_local` - local deterministic matching step
- `review_segment_glossary` - local/editor step
- `build_segment_pronouns` - AI prompt step
- `build_segment_pronouns_local` - local deterministic matching step
- `review_segment_pronouns` - local/editor step
- `build_segment_context` - AI prompt step
- `label_dialogue` - AI prompt step
- `translate` - AI prompt step
- `qa` - AI prompt step, optional
- `fix` - AI prompt step, optional

### The normal loop

1. Select a volume, chapter, or segment in the navigation tree.
2. Choose the relevant workflow step in **Prompt Studio**.
3. Let the app build the input JSON and render the prompt template.
4. Send that prompt to an LLM manually.
5. Paste the model response back into the app.
6. Validate and import the response.
7. Review and edit the resulting artifacts in **Editor**.
8. Repeat until the volume is ready for release.

This is deliberately boring. Boring is good when you are trying not to corrupt a novel.

## Project Data Layout

Project workspaces live under `data/<project_name>/`. The app opens existing projects from there.

```text
data/<project_name>/
  project_config.json
  source/
    volume_01.json
  segments/
    volume_01.segments.json
  prompts/                              # optional project-level prompt overrides
  canon/
    glossary/
      drafts/
      finalized/
      active/
    relationships/
      drafts/
      finalized/
      active/
    segment_pronouns/
    series/
      glossary.series.json
      relationships.series.json
      logs/
  working/
    glossary_extractions/
    relationship_extractions/
    segment_glossaries/
    segment_contexts/
    dialogue_labels/
    translations/
      draft/
      qa/
      fixed/
  release/
```

Important details from `manual_studio/core/workspace.py`:

- `project_config.json` defaults to:

```json
{
  "name": "<project_name>",
  "genre": "",
  "level": "Heavy",
  "enabled_steps": []
}
```

- `source/volume_XX.json` can be either a top-level list of chapter records or an object with a `chapters` list.
- Chapter records are expected to contain at least `chapter`, `name`, and `content`.
- `segments/volume_XX.segments.json` can be either a top-level list of segment records or an object with a `segments` list.
- Segment records are expected to contain at least `chapter`, `name`, `segment`, and `content`.
- Prompt lookup order is `data/<project_name>/prompts/`, then `data/prompts/`, then repo root `prompts/`.

Most writes create timestamped `.bak` backups before overwriting the target file.

## Series Canon Concept

This repo distinguishes between several canon layers on purpose.

- **Volume glossary / volume relationships**: the current volume's draft and finalized canon artifacts.
- **Finalized volume canon**: what you explicitly approved for that volume, stored under `canon/glossary/finalized/` and `canon/relationships/finalized/`.
- **Series glossary / series relationships**: long-lived cross-volume canon stored under `canon/series/`.
- **Active volume glossary / active volume relationships**: a filtered per-volume working subset built from the series canon against the current volume's actual source text and active character tokens.

Why this matters:

- Finalized volume canon is the thing you trust for that specific book.
- Series canon is how you stop volume 7 from "discovering" a new translation for a character introduced in volume 1.
- Active volume canon keeps prompts focused by pulling in only the series entries that actually matter for the current volume, instead of dumping your entire franchise bible into every step.

## Installation

The tracked requirements in `requirements.txt` are:

- `openai`
- `python-dotenv`
- `PyQt6`

Install from the repo root:

```bash
git clone <your-fork-or-this-repo-url>
cd translate-LN-pipeline

python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Run the main app:

```bash
python -m manual_studio.qt_app
```

Optional extras:

- EPUB export in **Release Center** requires `ebooklib`, which is **not** currently included in `requirements.txt`.

```bash
pip install ebooklib
```

- Adding EPUBs to Calibre requires `calibredb` to be installed and available on your `PATH`.

Legacy entry points such as `manual_prompt_studio.py`, `run.py`, `release_builder.py`, and the older `src/` CLI still exist, but they are not the recommended starting path for new users.

## Basic Usage Guide

### First run

1. Create or prepare a project folder under `data/<project_name>/`.
2. Add `source/volume_XX.json` files.
3. Add `segments/volume_XX.segments.json` files.
4. Optionally create `project_config.json` and set `genre` if you want prompt templates to receive genre context.
5. Start Manual Studio with `python -m manual_studio.qt_app`.
6. In the project selector, choose the repo root and an existing project under `data/`.

### Typical working flow

1. Start with volume-level canon: extract chapter glossary, merge volume glossary, review/edit it in **Editor**, approve it, then do the same for relationships.
2. If you are working across volumes, use **Series Canon** to initialize, build active canon, and sync finalized volume canon back into series canon.
3. For each segment, build or import segment glossary, segment pronouns, segment context, and dialogue labels.
4. Translate the labeled segment.
5. Run optional QA and fix passes.
6. Review and edit translations in **Editor**.
7. Build release artifacts in **Release Center**.

### Practical caveat

The current main app expects source and segment files to already exist. It does **not** currently create a project for you or generate segment files from raw chapters. If you need segmentation, use your own prep scripts or older tooling already present in the repo.

## Prompt System

Prompts are plain text templates. `manual_studio/core/prompt_engine.py` injects:

- `{{JSON_OUTPUT_POLICY}}`
- `{{INPUT_JSON}}`
- `{{genre}}`

The bundled JSON policy currently says:

- return strict JSON only
- no markdown
- no code fences
- no comments
- use `null` when unknown
- use `[]` for empty arrays
- confidence values should be numbers from `0` to `1`

Prompt customization is real and supported. You can override prompt files by placing them in:

- `data/<project_name>/prompts/`
- or `data/prompts/`

Manual Studio does **not** automatically send prompts to an API. You generate the prompt, run it against your model manually, and paste the response back.

## Artifact Import and Export

Imported AI responses are expected to be **top-level JSON objects**.

The response parser is forgiving about messy paste-ins:

- it strips fenced code blocks
- it can recover a surrounding JSON object from extra text

Clean JSON is still strongly recommended.

Storage format depends on the step:

- Chapter and segment workflow artifacts are usually stored as JSONL rows with wrapper fields like `item_id`, `status`, and `result`.
- Volume merge outputs are written as draft JSON files.
- Finalization happens by approving draft canon into finalized canon.

Examples:

- `working/glossary_extractions/volume_01.glossary_extractions.jsonl`
- `working/segment_glossaries/volume_01.segment_glossaries.jsonl`
- `working/dialogue_labels/volume_01.dialogue_labels.jsonl`
- `working/translations/draft/volume_01.translated.jsonl`
- `canon/glossary/drafts/volume_01.glossary.draft.json`
- `canon/glossary/finalized/volume_01.glossary.json`

## Development Notes

High-level architecture:

- `manual_studio/core/`: workflow services, workspace paths, prompt rendering, artifact storage, progress tracking, release building, and series canon logic
- `manual_studio/ui/`: PyQt6 pages and editor widgets
- `prompts/`: prompt templates used by the manual workflow
- `data/`: project workspaces and artifacts

For contributors:

- Treat the code as the source of truth.
- Keep this README aligned with `manual_studio/core/step_registry.py` and `manual_studio/core/workspace.py`.
- If the UI exposes something that is only partial, document it honestly instead of pretending it is finished.

## Limitations / Current Status

- Manual Studio v3 is the main app, but several registered local workflow steps still return placeholder messages in `ManualWorkflowService`: `review_volume_glossary`, `review_volume_relationships`, `review_segment_glossary`, `review_segment_pronouns`, and `assemble`.
- That does **not** mean editing is missing. The **Editor** tab already supports real editing for volume glossary, volume relationships, segment glossaries, segment pronouns, dialogue labels, and translations.
- Segment contexts and QA are currently preview/read-only in the Editor.
- Release building exists and works in **Release Center**, but its default output folder is `data/<project_name>/release_ui/`, while older workspace helpers and progress tracking still also know about `release/volume_XX.vi.json` and `release/volume_XX.vi.md`.
- Dialogue labeling is slightly transitional right now: `prompts/08_label_dialogue.txt` only guarantees `labeled_source`, but editor and review tooling also understand optional `units`.
- `project_config.json` includes `enabled_steps`, but the current GUI does not use that field as a hard workflow gate.
- The main app does not perform built-in API calls and does not generate segments for you.
- Optional EPUB export requires `ebooklib`, which is not currently installed by `requirements.txt`.

## Philosophy

- AI is useful for long-fiction translation, but it is unreliable if you let it freestyle.
- This project reduces fear by forcing structure: explicit canon layers, stored artifacts, review points, and repeatable release steps.
- It chooses control over convenience on purpose.

If you want a machine to do everything for you, this repo will feel stubborn. If you want a machine that can help without being trusted blindly, that stubbornness is the feature.
