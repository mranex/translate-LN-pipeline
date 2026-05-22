from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_store import ArtifactStore
from .jsonio import item_id_from_record, read_json, read_jsonl, result
from .project_index import ProjectIndex
from .prompt_engine import PromptEngine
from .response_parser import parse_json_response
from .series_canon import ActiveCanonResult, SeriesActionResult, SeriesCanonService
from .step_registry import STEPS_BY_ID, Step, steps_for_scope
from .workspace import Workspace


@dataclass(frozen=True)
class SelectionContext:
    scope: str
    volume: int
    chapter: int | None = None
    segment: str | None = None


@dataclass(frozen=True)
class PromptBuildResult:
    step_id: str
    prompt_name: str | None
    input_json: dict[str, Any] | None
    prompt_text: str | None
    is_local_action: bool = False
    message: str = ""


@dataclass(frozen=True)
class ImportResult:
    step_id: str
    item_id: str | None
    artifact_path: str | None
    wrote: bool
    message: str


@dataclass(frozen=True)
class LocalActionResult:
    step_id: str
    item_id: str | None
    artifact_path: str | None
    wrote: bool
    message: str
    payload: dict[str, Any] | None = None


class ManualWorkflowService:
    _LOCAL_ACTION_MESSAGES = {
        "review_volume_glossary": "Local/editor action only. Volume glossary review will be integrated in a later phase.",
        "review_volume_relationships": "Local/editor action only. Volume relationships review will be integrated in a later phase.",
        "review_segment_glossary": "Local/editor action only. Segment glossary review will be integrated in a later phase.",
        "review_segment_pronouns": "Local/editor action only. Segment pronoun review will be integrated in a later phase.",
        "assemble": "Local action only. Assemble will be integrated in a later phase.",
    }

    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.index = ProjectIndex(workspace)
        self.prompt_engine = PromptEngine(workspace)
        self.artifact_store = ArtifactStore(workspace)
        self.series_canon = SeriesCanonService(workspace)

    def available_steps(self, scope: str) -> list[Step]:
        return list(steps_for_scope(scope))

    def build_input(self, step_id: str, ctx: SelectionContext) -> dict[str, Any]:
        step = self._get_step(step_id)
        self._validate_scope(step, ctx)
        if step.is_local_action:
            raise ValueError(f"Step '{step_id}' is a local/review action and does not build prompt input.")

        if step_id == "extract_chapter_glossary":
            return self._base_chapter(ctx)
        if step_id == "extract_chapter_relationships":
            chapter = self._base_chapter(ctx)
            chapter["volume_glossary"] = self._load_glossary_final_first(ctx.volume)
            return chapter
        if step_id == "merge_volume_glossary":
            return {
                "volume": ctx.volume,
                "chapter_extractions": self._success_results(self.workspace.glossary_extractions(ctx.volume)),
                "previous_finalized_glossary": self._load_glossary_merge_baseline(ctx.volume),
            }
        if step_id == "merge_volume_relationships":
            return {
                "volume": ctx.volume,
                "relationship_extractions": self._success_results(self.workspace.relationship_extractions(ctx.volume)),
                "previous_finalized_relationships": self._load_relationships_merge_baseline(ctx.volume),
            }
        if step_id == "build_segment_glossary":
            segment = self._base_segment(ctx)
            segment["volume_glossary"] = self._load_glossary_final_first(ctx.volume)
            return segment
        if step_id == "build_segment_pronouns":
            segment = self._base_segment(ctx)
            segment["segment_glossary"] = self._jsonl_result(self.workspace.segment_glossaries(ctx.volume), segment["segment"])
            segment["volume_relationship_pronoun_canon"] = self._load_relationships_final_first(ctx.volume)
            return segment
        if step_id == "build_segment_context":
            segment = self._base_segment(ctx)
            segment["segment_glossary"] = self._jsonl_result(self.workspace.segment_glossaries(ctx.volume), segment["segment"])
            segment["segment_pronoun_table"] = self._jsonl_result(self.workspace.segment_pronouns(ctx.volume), segment["segment"])
            return segment
        if step_id == "label_dialogue":
            segment = self._base_segment(ctx)
            segment["segment_glossary"] = self._jsonl_result(self.workspace.segment_glossaries(ctx.volume), segment["segment"])
            segment["segment_pronoun_table"] = self._jsonl_result(self.workspace.segment_pronouns(ctx.volume), segment["segment"])
            segment["segment_context"] = self._jsonl_result(self.workspace.segment_contexts(ctx.volume), segment["segment"])
            segment["dialogue_labeling_config"] = {
                "review_confidence_threshold": 0.72,
                "auto_accept_confidence_threshold": 0.82,
            }
            return segment
        if step_id == "translate":
            segment = self._base_segment(ctx)
            segment.pop("content", None)
            segment["segment_glossary"] = self._jsonl_result(self.workspace.segment_glossaries(ctx.volume), segment["segment"])
            segment["segment_pronoun_table"] = self._jsonl_result(self.workspace.segment_pronouns(ctx.volume), segment["segment"])
            segment["segment_context"] = self._jsonl_result(self.workspace.segment_contexts(ctx.volume), segment["segment"])
            segment["dialogue_labels"] = self._jsonl_result(self.workspace.dialogue_labels(ctx.volume), segment["segment"])
            return segment
        if step_id == "qa":
            segment = self._base_segment(ctx)
            segment["source_content"] = segment.pop("content", "")
            segment["segment_glossary"] = self._jsonl_result(self.workspace.segment_glossaries(ctx.volume), segment["segment"])
            segment["segment_pronoun_table"] = self._jsonl_result(self.workspace.segment_pronouns(ctx.volume), segment["segment"])
            segment["segment_context"] = self._jsonl_result(self.workspace.segment_contexts(ctx.volume), segment["segment"])
            segment["dialogue_labels"] = self._jsonl_result(self.workspace.dialogue_labels(ctx.volume), segment["segment"])
            segment["translation"] = self._jsonl_result(self.workspace.draft_translations(ctx.volume), segment["segment"])
            return segment
        if step_id == "fix":
            segment = self.build_input("qa", ctx)
            segment["qa_report"] = self._jsonl_result(self.workspace.qa_reports(ctx.volume), segment["segment"])
            return segment

        raise ValueError(f"Unsupported workflow step: {step_id}")

    def render_prompt(self, step_id: str, ctx: SelectionContext) -> PromptBuildResult:
        step = self._get_step(step_id)
        self._validate_scope(step, ctx)
        if step.is_local_action:
            return PromptBuildResult(
                step_id=step.id,
                prompt_name=None,
                input_json=None,
                prompt_text=None,
                is_local_action=True,
                message=self._LOCAL_ACTION_MESSAGES.get(step.id, step.description or "Local action only."),
            )

        input_json = self.build_input(step_id, ctx)
        prompt_text = self.prompt_engine.render(step.prompt, input_json)
        return PromptBuildResult(
            step_id=step.id,
            prompt_name=step.prompt,
            input_json=input_json,
            prompt_text=prompt_text,
        )

    def validate_response_text(self, text: str) -> dict[str, Any]:
        return parse_json_response(text)

    def import_response(self, step_id: str, ctx: SelectionContext, response_obj: dict[str, Any]) -> ImportResult:
        step = self._get_step(step_id)
        self._validate_scope(step, ctx)
        if not isinstance(response_obj, dict):
            raise ValueError("Response object must be a JSON object.")

        if step.is_local_action:
            return ImportResult(
                step_id=step.id,
                item_id=None,
                artifact_path=None,
                wrote=False,
                message=self._LOCAL_ACTION_MESSAGES.get(step.id, "Local action only."),
            )

        if step_id == "extract_chapter_glossary":
            item_id = self._chapter_item_id(ctx)
            path = self.workspace.glossary_extractions(ctx.volume)
            self.artifact_store.upsert_jsonl(path, item_id, response_obj)
            return self._jsonl_result_info(step.id, item_id, path)
        if step_id == "merge_volume_glossary":
            path = self.artifact_store.write_glossary_draft(ctx.volume, response_obj)
            return ImportResult(step.id, None, str(path), True, "Wrote glossary draft JSON.")
        if step_id == "extract_chapter_relationships":
            item_id = self._chapter_item_id(ctx)
            path = self.workspace.relationship_extractions(ctx.volume)
            self.artifact_store.upsert_jsonl(path, item_id, response_obj)
            return self._jsonl_result_info(step.id, item_id, path)
        if step_id == "merge_volume_relationships":
            path = self.artifact_store.write_relationships_draft(ctx.volume, response_obj)
            return ImportResult(step.id, None, str(path), True, "Wrote relationships draft JSON.")
        if step_id == "build_segment_glossary":
            return self._import_segment_jsonl(step.id, ctx, self.workspace.segment_glossaries(ctx.volume), response_obj)
        if step_id == "build_segment_pronouns":
            return self._import_segment_jsonl(step.id, ctx, self.workspace.segment_pronouns(ctx.volume), response_obj)
        if step_id == "build_segment_context":
            return self._import_segment_jsonl(step.id, ctx, self.workspace.segment_contexts(ctx.volume), response_obj)
        if step_id == "label_dialogue":
            return self._import_segment_jsonl(step.id, ctx, self.workspace.dialogue_labels(ctx.volume), response_obj)
        if step_id == "translate":
            return self._import_segment_jsonl(step.id, ctx, self.workspace.draft_translations(ctx.volume), response_obj)
        if step_id == "qa":
            return self._import_segment_jsonl(step.id, ctx, self.workspace.qa_reports(ctx.volume), response_obj)
        if step_id == "fix":
            return self._import_segment_jsonl(step.id, ctx, self.workspace.fixed_translations(ctx.volume), response_obj)

        raise ValueError(f"Unsupported import step: {step_id}")

    def run_local_action(self, step_id: str, ctx: SelectionContext) -> LocalActionResult:
        step = self._get_step(step_id)
        self._validate_scope(step, ctx)
        if not step.is_local_action:
            raise ValueError(f"Step '{step.id}' is prompt-backed and cannot be run as a local action.")

        if step_id == "initialize_series_glossary_from_volume":
            return self._series_action_to_local_result(
                step.id,
                self.series_canon.initialize_series_glossary_from_volume(ctx.volume),
            )
        if step_id == "initialize_series_relationships_from_volume":
            return self._series_action_to_local_result(
                step.id,
                self.series_canon.initialize_series_relationships_from_volume(ctx.volume),
            )
        if step_id == "build_active_volume_glossary":
            return self._active_canon_to_local_result(
                step.id,
                self.series_canon.build_active_volume_glossary(ctx.volume, write=True),
            )
        if step_id == "build_active_volume_relationships":
            return self._active_canon_to_local_result(
                step.id,
                self.series_canon.build_active_volume_relationships(ctx.volume, write=True),
            )
        if step_id == "sync_volume_glossary_to_series":
            return self._series_action_to_local_result(
                step.id,
                self.series_canon.sync_volume_glossary_to_series(ctx.volume),
            )
        if step_id == "sync_volume_relationships_to_series":
            return self._series_action_to_local_result(
                step.id,
                self.series_canon.sync_volume_relationships_to_series(ctx.volume),
            )
        if step_id == "build_segment_glossary_local":
            return self._run_local_segment_glossary(ctx)
        if step_id == "build_segment_pronouns_local":
            return self._run_local_segment_pronouns(ctx)
        if step_id in {"review_segment_glossary", "review_segment_pronouns"}:
            return LocalActionResult(
                step_id=step.id,
                item_id=self._segment_item_id(ctx) if ctx.scope == "segment" else None,
                artifact_path=None,
                wrote=False,
                message=self._LOCAL_ACTION_MESSAGES.get(step.id, step.description or "Local action only."),
            )
        return LocalActionResult(
            step_id=step.id,
            item_id=None,
            artifact_path=None,
            wrote=False,
            message=self._LOCAL_ACTION_MESSAGES.get(step.id, step.description or "Local action only."),
        )

    def _import_segment_jsonl(
        self,
        step_id: str,
        ctx: SelectionContext,
        path: Path,
        response_obj: dict[str, Any],
    ) -> ImportResult:
        item_id = self._segment_item_id(ctx)
        self.artifact_store.upsert_jsonl(path, item_id, response_obj)
        return self._jsonl_result_info(step_id, item_id, path)

    def _jsonl_result_info(self, step_id: str, item_id: str, path: Path) -> ImportResult:
        return ImportResult(
            step_id=step_id,
            item_id=item_id,
            artifact_path=str(path),
            wrote=True,
            message="Wrote JSONL artifact row.",
        )

    def _series_action_to_local_result(self, step_id: str, result_obj: SeriesActionResult) -> LocalActionResult:
        return self._local_result_info(
            step_id=step_id,
            item_id=None,
            path=result_obj.path,
            wrote=result_obj.wrote,
            message=self._format_series_action_message(result_obj),
            payload=result_obj.payload,
        )

    def _active_canon_to_local_result(self, step_id: str, result_obj: ActiveCanonResult) -> LocalActionResult:
        return self._local_result_info(
            step_id=step_id,
            item_id=None,
            path=result_obj.path,
            wrote=result_obj.wrote,
            message=self._format_active_canon_message(result_obj),
            payload=result_obj.payload,
        )

    def _local_result_info(
        self,
        step_id: str,
        item_id: str | None,
        path: Path | None,
        wrote: bool,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> LocalActionResult:
        return LocalActionResult(
            step_id=step_id,
            item_id=item_id,
            artifact_path=str(path) if path is not None else None,
            wrote=wrote,
            message=message,
            payload=payload,
        )

    def _format_series_action_message(self, result_obj: SeriesActionResult) -> str:
        message = result_obj.message
        details: list[str] = []
        if result_obj.added_count or result_obj.skipped_count or result_obj.conflict_count:
            details.append(
                f"added={result_obj.added_count}, skipped={result_obj.skipped_count}, conflicts={result_obj.conflict_count}"
            )
        if result_obj.path is not None:
            details.append(f"path={result_obj.path}")
        if not result_obj.wrote and result_obj.path is None:
            return message
        if not details:
            return message
        return f"{message} ({'; '.join(details)})"

    def _format_active_canon_message(self, result_obj: ActiveCanonResult) -> str:
        details = [
            f"matched={result_obj.matched_count}/{result_obj.total_series_entries}",
        ]
        if result_obj.path is not None:
            details.append(f"path={result_obj.path}")
        return f"{result_obj.message} ({'; '.join(details)})"

    def _run_local_segment_glossary(self, ctx: SelectionContext) -> LocalActionResult:
        segment_record = self._segment_record(ctx)
        item_id = self._segment_item_id(ctx)
        segment_id = str(segment_record.get("segment"))
        glossary = self._load_glossary_final_first(ctx.volume)
        entries = glossary.get("volume_merge_glossary") or glossary.get("entries") or []
        content = segment_record.get("content", "") or ""

        matched_entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source", "")
            if source and source in content:
                matched_entries.append(entry)

        notes = ["Built locally from volume glossary by exact source-string matching."]
        if not matched_entries:
            notes.append("No volume glossary source strings matched this segment.")

        result_obj = {
            "item_id": item_id,
            "chapter": segment_record.get("chapter", 0),
            "segment": segment_id,
            "segment_glossary": matched_entries,
            "deterministic_source_hits": matched_entries,
            "missing_glossary_candidates": [],
            "local_build": True,
            "notes": notes,
        }
        path = self.workspace.segment_glossaries(ctx.volume)
        self.artifact_store.upsert_jsonl(path, item_id, result_obj)
        return self._local_result_info(
            step_id="build_segment_glossary_local",
            item_id=item_id,
            path=path,
            wrote=True,
            message=f"Built segment glossary locally with {len(matched_entries)} exact source-string hits.",
            payload=result_obj,
        )

    def _run_local_segment_pronouns(self, ctx: SelectionContext) -> LocalActionResult:
        segment_record = self._segment_record(ctx)
        item_id = self._segment_item_id(ctx)
        segment_id = str(segment_record.get("segment"))
        glossary = self.artifact_store.load_glossary(ctx.volume)
        relationships = self.artifact_store.load_relationships(ctx.volume)
        glossary_entries = glossary.get("volume_merge_glossary", [])
        relationship_rows = relationships.get("relationship_pronoun_canon", [])
        content = segment_record.get("content", "") or ""

        present_chars: set[str] = set()
        for term in glossary_entries:
            if not isinstance(term, dict):
                continue
            if term.get("type") in ["character", "alias", "title", "epithet"]:
                source = term.get("source", "")
                if source and source in content:
                    present_chars.add(term.get("vi", ""))
                    present_chars.add(term.get("source", ""))
                    present_chars.add(term.get("id", ""))

        pronoun_rows = []
        for rel in relationship_rows:
            if not isinstance(rel, dict):
                continue
            speaker = rel.get("speaker")
            listener = rel.get("listener")
            speaker_in = (speaker in present_chars) or (speaker in ["UNKNOWN", "GROUP"])
            listener_in = (listener in present_chars) or (listener in ["UNKNOWN", "GROUP", "self", "SELF"])
            if speaker_in and listener_in:
                pronoun_rows.append(
                    {
                        "speaker": speaker,
                        "listener": listener,
                        "relationship": rel.get("relationship", ""),
                        "self": rel.get("self", ""),
                        "other": rel.get("other", ""),
                        "variants": rel.get("variants", []),
                        "source": "inherited_from_volume",
                        "notes": rel.get("notes", ""),
                    }
                )

        result_obj = {
            "item_id": item_id,
            "chapter": segment_record.get("chapter", 0),
            "segment": segment_id,
            "segment_pronoun_table": pronoun_rows,
            "segment_override_candidates": [],
            "missing_rules": [],
        }
        path = self.workspace.segment_pronouns(ctx.volume)
        self.artifact_store.upsert_jsonl(path, item_id, result_obj)
        return self._local_result_info(
            step_id="build_segment_pronouns_local",
            item_id=item_id,
            path=path,
            wrote=True,
            message=f"Built segment pronouns locally with {len(pronoun_rows)} inherited rules.",
            payload=result_obj,
        )

    def _get_step(self, step_id: str) -> Step:
        step = STEPS_BY_ID.get(step_id)
        if step is None:
            raise ValueError(f"Unknown workflow step: {step_id}")
        return step

    def _validate_scope(self, step: Step, ctx: SelectionContext) -> None:
        if step.scope != ctx.scope:
            raise ValueError(
                f"Step '{step.id}' requires scope '{step.scope}', but received '{ctx.scope}'."
            )

    def _base_chapter(self, ctx: SelectionContext) -> dict[str, Any]:
        record = self._chapter_record(ctx)
        return {
            "item_id": item_id_from_record(record),
            "volume": ctx.volume,
            "chapter": record.get("chapter"),
            "segment": record.get("segment"),
            "name": record.get("name"),
            "content": record.get("content", ""),
        }

    def _base_segment(self, ctx: SelectionContext) -> dict[str, Any]:
        record = self._segment_record(ctx)
        return {
            "item_id": item_id_from_record(record),
            "volume": ctx.volume,
            "chapter": record.get("chapter"),
            "segment": record.get("segment"),
            "name": record.get("name"),
            "content": record.get("content", ""),
        }

    def _chapter_item_id(self, ctx: SelectionContext) -> str:
        return item_id_from_record(self._chapter_record(ctx))

    def _segment_item_id(self, ctx: SelectionContext) -> str:
        return item_id_from_record(self._segment_record(ctx))

    def _chapter_record(self, ctx: SelectionContext) -> dict[str, Any]:
        if ctx.chapter is None:
            raise ValueError("Chapter selection is required for this step.")
        for record in self.index.get_chapter_records(ctx.volume):
            try:
                if int(record.get("chapter", 0)) == int(ctx.chapter):
                    return record
            except Exception:
                continue
        raise ValueError(f"Chapter {ctx.chapter} was not found in volume {ctx.volume}.")

    def _segment_record(self, ctx: SelectionContext) -> dict[str, Any]:
        if ctx.segment is None:
            raise ValueError("Segment selection is required for this step.")
        target = str(ctx.segment)
        for record in self.index.get_segment_records(ctx.volume):
            if str(record.get("segment")) == target:
                return record
        raise ValueError(f"Segment '{ctx.segment}' was not found in volume {ctx.volume}.")

    def _load_glossary_final_first(self, volume: int) -> dict[str, Any]:
        return read_json(
            self.workspace.glossary_final(volume),
            read_json(self.workspace.glossary_draft(volume), {}),
        )

    def _load_glossary_merge_baseline(self, volume: int) -> dict[str, Any] | None:
        active_path = self.workspace.active_volume_glossary(volume)
        if active_path.exists():
            return read_json(active_path, None)
        if volume > 1:
            return read_json(self.workspace.glossary_final(volume - 1), None)
        return None

    def _load_relationships_final_first(self, volume: int) -> dict[str, Any]:
        return read_json(
            self.workspace.relationships_final(volume),
            read_json(self.workspace.relationships_draft(volume), {}),
        )

    def _load_relationships_merge_baseline(self, volume: int) -> dict[str, Any] | None:
        active_path = self.workspace.active_volume_relationships(volume)
        if active_path.exists():
            return read_json(active_path, None)
        if volume > 1:
            return read_json(self.workspace.relationships_final(volume - 1), None)
        return None

    def _success_results(self, path: Path) -> list[Any]:
        return [row.get("result") for row in read_jsonl(path) if isinstance(row, dict) and row.get("status") == "success"]

    def _jsonl_result(self, path: Path, item_id: str) -> dict[str, Any]:
        row = self.workspace.map_jsonl(path).get(str(item_id), {})
        return result(row)
