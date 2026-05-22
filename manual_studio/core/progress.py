from __future__ import annotations

"""Read-only progress calculations for the manual workflow.

Smoke example:
    from manual_studio.core.workspace import Workspace
    from manual_studio.core.progress import ProgressService
    ws = Workspace.from_legacy(repo_root, project_name)
    progress = ProgressService(ws).volume_progress(1)
"""

from dataclasses import dataclass
from typing import Any

from .jsonio import iid, item_id_from_record, read_jsonl
from .project_index import ProjectIndex
from .step_registry import STEPS, Step
from .workspace import Workspace


@dataclass(frozen=True)
class StepProgress:
    step_id: str
    label: str
    scope: str
    total: int
    done: int
    missing: int
    percent: float
    status: str


class ProgressService:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.index = ProjectIndex(workspace)

    def volume_progress(self, volume: int) -> list[StepProgress]:
        context = self._build_context(volume)
        return [self._step_progress(step, context, query="volume") for step in STEPS]

    def chapter_progress(self, volume: int, chapter_id: str) -> list[StepProgress]:
        context = self._build_context(volume, chapter_id=chapter_id)
        return [self._step_progress(step, context, query="chapter") for step in STEPS]

    def segment_progress(self, volume: int, segment_id: str) -> list[StepProgress]:
        context = self._build_context(volume, segment_id=segment_id)
        return [self._step_progress(step, context, query="segment") for step in STEPS]

    def _build_context(
        self,
        volume: int,
        chapter_id: str | None = None,
        segment_id: str | None = None,
    ) -> dict[str, Any]:
        chapter_records = self.index.get_chapter_records(volume)
        segment_records = self.index.get_segment_records(volume)
        chapter_record = self._find_chapter_record(chapter_records, chapter_id)
        segment_record = self._find_segment_record(segment_records, segment_id)
        if chapter_record is None and segment_record is not None:
            chapter_record = self._find_chapter_by_number(chapter_records, segment_record.get("chapter"))
        chapter_segments = self._filter_segments_for_chapter(segment_records, chapter_record)
        return {
            "volume": volume,
            "source_exists": self.workspace.source(volume).exists(),
            "segments_exists": self.workspace.segments_file(volume).exists(),
            "chapter_records": chapter_records,
            "segment_records": segment_records,
            "chapter_record": chapter_record,
            "segment_record": segment_record,
            "chapter_segments": chapter_segments,
            "success_ids": self._success_ids_by_path(volume),
        }

    def _success_ids_by_path(self, volume: int) -> dict[str, set[str]]:
        return {
            "glossary_extractions": self._success_ids(self.workspace.glossary_extractions(volume)),
            "relationship_extractions": self._success_ids(self.workspace.relationship_extractions(volume)),
            "segment_glossaries": self._success_ids(self.workspace.segment_glossaries(volume)),
            "segment_pronouns": self._success_ids(self.workspace.segment_pronouns(volume)),
            "segment_contexts": self._success_ids(self.workspace.segment_contexts(volume)),
            "dialogue_labels": self._success_ids(self.workspace.dialogue_labels(volume)),
            "draft_translations": self._success_ids(self.workspace.draft_translations(volume)),
            "qa_reports": self._success_ids(self.workspace.qa_reports(volume)),
            "fixed_translations": self._success_ids(self.workspace.fixed_translations(volume)),
        }

    def _success_ids(self, path) -> set[str]:
        return {
            iid(row)
            for row in read_jsonl(path)
            if isinstance(row, dict) and row.get("status") == "success" and iid(row)
        }

    def _step_progress(self, step: Step, context: dict[str, Any], query: str) -> StepProgress:
        if step.id == "extract_chapter_glossary":
            return self._item_progress(
                step,
                self._chapter_item_ids(context, query),
                context["success_ids"]["glossary_extractions"],
                context["source_exists"],
            )
        if step.id == "extract_chapter_relationships":
            return self._item_progress(
                step,
                self._chapter_item_ids(context, query),
                context["success_ids"]["relationship_extractions"],
                context["source_exists"],
            )
        if step.id == "merge_volume_glossary":
            return self._artifact_progress(
                step,
                complete=self.workspace.glossary_draft(context["volume"]).exists()
                or self.workspace.glossary_final(context["volume"]).exists(),
            )
        if step.id == "review_volume_glossary":
            draft_exists = self.workspace.glossary_draft(context["volume"]).exists()
            final_exists = self.workspace.glossary_final(context["volume"]).exists()
            return self._finalize_progress(step, draft_exists=draft_exists, final_exists=final_exists)
        if step.id == "merge_volume_relationships":
            return self._artifact_progress(
                step,
                complete=self.workspace.relationships_draft(context["volume"]).exists()
                or self.workspace.relationships_final(context["volume"]).exists(),
            )
        if step.id == "review_volume_relationships":
            draft_exists = self.workspace.relationships_draft(context["volume"]).exists()
            final_exists = self.workspace.relationships_final(context["volume"]).exists()
            return self._finalize_progress(step, draft_exists=draft_exists, final_exists=final_exists)
        if step.id in {
            "build_segment_glossary",
            "build_segment_glossary_local",
            "review_segment_glossary",
        }:
            return self._item_progress(
                step,
                self._segment_item_ids(context, query),
                context["success_ids"]["segment_glossaries"],
                context["segments_exists"],
            )
        if step.id in {
            "build_segment_pronouns",
            "build_segment_pronouns_local",
            "review_segment_pronouns",
        }:
            return self._item_progress(
                step,
                self._segment_item_ids(context, query),
                context["success_ids"]["segment_pronouns"],
                context["segments_exists"],
            )
        if step.id == "build_segment_context":
            return self._item_progress(
                step,
                self._segment_item_ids(context, query),
                context["success_ids"]["segment_contexts"],
                context["segments_exists"],
            )
        if step.id == "label_dialogue":
            return self._item_progress(
                step,
                self._segment_item_ids(context, query),
                context["success_ids"]["dialogue_labels"],
                context["segments_exists"],
            )
        if step.id == "translate":
            done_ids = context["success_ids"]["draft_translations"] | context["success_ids"]["fixed_translations"]
            return self._item_progress(
                step,
                self._segment_item_ids(context, query),
                done_ids,
                context["segments_exists"],
            )
        if step.id == "qa":
            return self._item_progress(
                step,
                self._segment_item_ids(context, query),
                context["success_ids"]["qa_reports"],
                context["segments_exists"],
            )
        if step.id == "fix":
            return self._item_progress(
                step,
                self._segment_item_ids(context, query),
                context["success_ids"]["fixed_translations"],
                context["segments_exists"],
            )
        if step.id == "assemble":
            release_json_exists = self.workspace.release_json(context["volume"]).exists()
            release_md_exists = self.workspace.release_md(context["volume"]).exists()
            if release_json_exists and release_md_exists:
                return self._artifact_progress(step, complete=True)
            if release_json_exists or release_md_exists:
                return StepProgress(step.id, step.label, step.scope, 1, 0, 1, 50.0, "partial")
            return self._artifact_progress(step, complete=False)
        return StepProgress(step.id, step.label, step.scope, 0, 0, 0, 0.0, "unknown")

    def _item_progress(
        self,
        step: Step,
        item_ids: list[str] | None,
        done_ids: set[str],
        source_exists: bool,
    ) -> StepProgress:
        if not source_exists:
            return StepProgress(step.id, step.label, step.scope, 0, 0, 0, 0.0, "missing_source")
        if item_ids is None:
            return StepProgress(step.id, step.label, step.scope, 0, 0, 0, 0.0, "unknown")
        total = len(item_ids)
        done = sum(1 for item_id in item_ids if item_id in done_ids)
        return self._count_progress(step, total=total, done=done)

    def _count_progress(self, step: Step, total: int, done: int) -> StepProgress:
        missing = max(total - done, 0)
        if total == 0:
            return StepProgress(step.id, step.label, step.scope, 0, 0, 0, 0.0, "not_started")
        if done == 0:
            return StepProgress(step.id, step.label, step.scope, total, 0, missing, 0.0, "not_started")
        if done >= total:
            return StepProgress(step.id, step.label, step.scope, total, total, 0, 100.0, "done")
        percent = round((done / total) * 100.0, 2)
        return StepProgress(step.id, step.label, step.scope, total, done, missing, percent, "partial")

    def _artifact_progress(self, step: Step, complete: bool) -> StepProgress:
        if complete:
            return StepProgress(step.id, step.label, step.scope, 1, 1, 0, 100.0, "done")
        return StepProgress(step.id, step.label, step.scope, 1, 0, 1, 0.0, "not_started")

    def _finalize_progress(self, step: Step, draft_exists: bool, final_exists: bool) -> StepProgress:
        if final_exists:
            return StepProgress(step.id, step.label, step.scope, 1, 1, 0, 100.0, "done")
        if draft_exists:
            return StepProgress(step.id, step.label, step.scope, 1, 0, 1, 50.0, "partial")
        return StepProgress(step.id, step.label, step.scope, 1, 0, 1, 0.0, "not_started")

    def _chapter_item_ids(self, context: dict[str, Any], query: str) -> list[str] | None:
        if query == "volume":
            return [item_id_from_record(record) for record in context["chapter_records"]]
        if context["chapter_record"] is None:
            return None
        return [item_id_from_record(context["chapter_record"])]

    def _segment_item_ids(self, context: dict[str, Any], query: str) -> list[str] | None:
        if query == "volume":
            return [self._segment_id(record) for record in context["segment_records"]]
        if query == "chapter":
            if context["chapter_record"] is None:
                return None
            return [self._segment_id(record) for record in context["chapter_segments"]]
        if context["segment_record"] is None:
            return None
        return [self._segment_id(context["segment_record"])]

    def _find_chapter_record(self, records: list[dict[str, Any]], chapter_id: str | None) -> dict[str, Any] | None:
        if chapter_id is None:
            return None
        target = str(chapter_id)
        for record in records:
            if item_id_from_record(record) == target or str(record.get("chapter")) == target:
                return record
        return None

    def _find_chapter_by_number(self, records: list[dict[str, Any]], chapter_number: Any) -> dict[str, Any] | None:
        if chapter_number is None:
            return None
        for record in records:
            if record.get("chapter") == chapter_number:
                return record
        return None

    def _find_segment_record(self, records: list[dict[str, Any]], segment_id: str | None) -> dict[str, Any] | None:
        if segment_id is None:
            return None
        target = str(segment_id)
        for record in records:
            if self._segment_id(record) == target:
                return record
        return None

    def _filter_segments_for_chapter(
        self,
        records: list[dict[str, Any]],
        chapter_record: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if chapter_record is None:
            return []
        chapter_number = chapter_record.get("chapter")
        return [record for record in records if record.get("chapter") == chapter_number]

    def _segment_id(self, record: dict[str, Any]) -> str:
        return str(record.get("segment") or item_id_from_record(record))
