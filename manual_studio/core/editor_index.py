from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .jsonio import iid, read_jsonl, result
from .manual_workflow import SelectionContext
from .workspace import Workspace


@dataclass(frozen=True)
class EditorRow:
    values: dict[str, Any]
    raw: Any


@dataclass(frozen=True)
class ArtifactView:
    rows: tuple[EditorRow, ...] = ()
    artifact_path: str | None = None
    raw_object: Any = None
    error: str = ""
    message: str = ""


@dataclass(frozen=True)
class EditorSnapshot:
    volume_glossary: ArtifactView
    volume_relationships: ArtifactView
    segment_glossaries: ArtifactView
    segment_pronouns: ArtifactView
    segment_contexts: ArtifactView
    dialogue_labels: ArtifactView
    translations: ArtifactView

    @classmethod
    def empty(cls) -> "EditorSnapshot":
        empty_view = ArtifactView(message="No artifact data loaded.")
        return cls(
            volume_glossary=empty_view,
            volume_relationships=empty_view,
            segment_glossaries=empty_view,
            segment_pronouns=empty_view,
            segment_contexts=empty_view,
            dialogue_labels=empty_view,
            translations=empty_view,
        )


class EditorIndex:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        from .editor_actions import EditorActionService

        self.editor_actions = EditorActionService(workspace)

    def load_snapshot(self, ctx: SelectionContext) -> EditorSnapshot:
        segment_records, _segment_error = self._load_segment_records(ctx.volume)
        segment_to_chapter = {
            str(record.get("segment")): int(record.get("chapter", 0))
            for record in segment_records
            if record.get("segment") is not None
        }

        return EditorSnapshot(
            volume_glossary=self._load_volume_glossary(ctx),
            volume_relationships=self._load_volume_relationships(ctx),
            segment_glossaries=self._load_jsonl_view(
                path=self.workspace.segment_glossaries(ctx.volume),
                ctx=ctx,
                segment_to_chapter=segment_to_chapter,
                summarizer=self._summarize_segment_glossary,
                empty_message="No segment glossary rows found for this selection.",
            ),
            segment_pronouns=self._load_jsonl_view(
                path=self.workspace.segment_pronouns(ctx.volume),
                ctx=ctx,
                segment_to_chapter=segment_to_chapter,
                summarizer=self._summarize_segment_pronouns,
                empty_message="No segment pronoun rows found for this selection.",
            ),
            segment_contexts=self._load_jsonl_view(
                path=self.workspace.segment_contexts(ctx.volume),
                ctx=ctx,
                segment_to_chapter=segment_to_chapter,
                summarizer=self._summarize_segment_context,
                empty_message="No segment context rows found for this selection.",
            ),
            dialogue_labels=self._load_jsonl_view(
                path=self.workspace.dialogue_labels(ctx.volume),
                ctx=ctx,
                segment_to_chapter=segment_to_chapter,
                summarizer=self._summarize_dialogue_labels,
                empty_message="No dialogue label rows found for this selection.",
            ),
            translations=self._load_translations(ctx, segment_records, segment_to_chapter),
        )

    def _load_volume_glossary(self, ctx: SelectionContext) -> ArtifactView:
        try:
            obj = self.editor_actions.load_volume_glossary(ctx.volume)
        except Exception as exc:
            path = self.workspace.glossary_draft(ctx.volume)
            if not path.exists():
                path = self.workspace.glossary_final(ctx.volume)
            return ArtifactView(artifact_path=str(path), error=f"Failed to load glossary JSON: {exc}")

        path = self.workspace.glossary_draft(ctx.volume)
        if not path.exists():
            path = self.workspace.glossary_final(ctx.volume)
        artifact_path = str(path) if path.exists() else str(self.workspace.glossary_draft(ctx.volume))

        rows = []
        for entry in obj.get("volume_merge_glossary") or []:
            if not isinstance(entry, dict):
                continue
            rows.append(
                EditorRow(
                    values={
                        "id": entry.get("id", ""),
                        "source": entry.get("source", ""),
                        "vi": entry.get("vi", ""),
                        "type": entry.get("type", ""),
                        "status": entry.get("status", ""),
                        "notes": entry.get("notes", ""),
                        "needs_human_review": entry.get("needs_human_review", ""),
                        "variants_count": len(entry.get("variants") or []),
                        "aliases_count": len(entry.get("aliases") or []),
                        "forbidden_translations_count": len(entry.get("forbidden_translations") or []),
                        "appears_in_count": len(entry.get("appears_in") or []),
                    },
                    raw=entry,
                )
            )
        return ArtifactView(
            rows=tuple(rows),
            artifact_path=artifact_path,
            raw_object=obj,
            message="" if rows else "No volume glossary rows found in the selected artifact.",
        )

    def _load_volume_relationships(self, ctx: SelectionContext) -> ArtifactView:
        try:
            obj = self.editor_actions.load_volume_relationships(ctx.volume)
        except Exception as exc:
            path = self.workspace.relationships_draft(ctx.volume)
            if not path.exists():
                path = self.workspace.relationships_final(ctx.volume)
            return ArtifactView(artifact_path=str(path), error=f"Failed to load relationships JSON: {exc}")

        path = self.workspace.relationships_draft(ctx.volume)
        if not path.exists():
            path = self.workspace.relationships_final(ctx.volume)
        artifact_path = str(path) if path.exists() else str(self.workspace.relationships_draft(ctx.volume))

        rows = []
        for entry in obj.get("relationship_pronoun_canon") or []:
            if not isinstance(entry, dict):
                continue
            rows.append(
                EditorRow(
                    values={
                        "id": entry.get("id", ""),
                        "speaker": entry.get("speaker", ""),
                        "listener": entry.get("listener", ""),
                        "relationship": entry.get("relationship", ""),
                        "self": entry.get("self", ""),
                        "other": entry.get("other", ""),
                        "scope": entry.get("scope", ""),
                        "status": entry.get("status", ""),
                        "notes": entry.get("notes", ""),
                        "needs_human_review": entry.get("needs_human_review", ""),
                        "variants_count": len(entry.get("variants") or []),
                    },
                    raw=entry,
                )
            )
        return ArtifactView(
            rows=tuple(rows),
            artifact_path=artifact_path,
            raw_object=obj,
            message="" if rows else "No volume relationship rows found in the selected artifact.",
        )

    def _load_jsonl_view(
        self,
        path,
        ctx: SelectionContext,
        segment_to_chapter: dict[str, int],
        summarizer: Callable[[dict[str, Any]], EditorRow],
        empty_message: str,
    ) -> ArtifactView:
        if not path.exists():
            return ArtifactView(artifact_path=str(path), message=empty_message)
        try:
            rows = read_jsonl(path)
        except Exception as exc:
            return ArtifactView(artifact_path=str(path), error=f"Failed to load JSONL: {exc}")

        filtered = [row for row in rows if self._row_matches_context(row, ctx, segment_to_chapter)]
        summary_rows = [summarizer(row) for row in filtered if isinstance(row, dict)]
        return ArtifactView(
            rows=tuple(summary_rows),
            artifact_path=str(path),
            message="" if summary_rows else empty_message,
        )

    def _load_translations(
        self,
        ctx: SelectionContext,
        segment_records: list[dict[str, Any]],
        segment_to_chapter: dict[str, int],
    ) -> ArtifactView:
        draft_rows, draft_error = self._load_jsonl_rows(self.workspace.draft_translations(ctx.volume))
        fixed_rows, fixed_error = self._load_jsonl_rows(self.workspace.fixed_translations(ctx.volume))
        qa_rows, qa_error = self._load_jsonl_rows(self.workspace.qa_reports(ctx.volume))

        if draft_error:
            return ArtifactView(artifact_path=str(self.workspace.draft_translations(ctx.volume)), error=draft_error)
        if fixed_error:
            return ArtifactView(artifact_path=str(self.workspace.fixed_translations(ctx.volume)), error=fixed_error)
        if qa_error:
            return ArtifactView(artifact_path=str(self.workspace.qa_reports(ctx.volume)), error=qa_error)

        draft_map = {iid(row): row for row in draft_rows if isinstance(row, dict) and iid(row)}
        fixed_map = {iid(row): row for row in fixed_rows if isinstance(row, dict) and iid(row)}
        qa_map = {iid(row): row for row in qa_rows if isinstance(row, dict) and iid(row)}

        relevant_ids = self._relevant_segment_ids(ctx, segment_records, draft_map, fixed_map, qa_map)
        rows = []
        for item_id in relevant_ids:
            draft_row = draft_map.get(item_id)
            fixed_row = fixed_map.get(item_id)
            qa_row = qa_map.get(item_id)
            draft_result = result(draft_row) if isinstance(draft_row, dict) else {}
            fixed_result = result(fixed_row) if isinstance(fixed_row, dict) else {}
            preview = (
                self.editor_actions.summarize_translation(fixed_result if isinstance(fixed_result, dict) else None)
                or self.editor_actions.summarize_translation(draft_result if isinstance(draft_result, dict) else None)
            )
            rows.append(
                EditorRow(
                    values={
                        "item_id": item_id,
                        "draft_exists": bool(draft_row),
                        "fixed_exists": bool(fixed_row),
                        "qa_exists": bool(qa_row),
                        "translation_preview": self._preview_text(preview),
                    },
                    raw={
                        "item_id": item_id,
                        "draft": draft_row,
                        "fixed": fixed_row,
                        "qa": qa_row,
                    },
                )
            )

        return ArtifactView(
            rows=tuple(rows),
            artifact_path=str(self.workspace.draft_translations(ctx.volume)),
            message="" if rows else "No translation artifacts found for this selection.",
        )

    def _load_jsonl_rows(self, path) -> tuple[list[Any], str]:
        if not path.exists():
            return [], ""
        try:
            return read_jsonl(path), ""
        except Exception as exc:
            return [], f"Failed to load JSONL from {path}: {exc}"

    def _load_segment_records(self, volume: int) -> tuple[list[dict[str, Any]], str]:
        path = self.workspace.segments_file(volume)
        if not path.exists():
            return [], ""
        try:
            records = self.workspace.segments(volume)
        except Exception as exc:
            return [], f"Failed to load segment records from {path}: {exc}"
        return [record for record in records if isinstance(record, dict)], ""

    def _row_matches_context(
        self,
        row: dict[str, Any],
        ctx: SelectionContext,
        segment_to_chapter: dict[str, int],
    ) -> bool:
        if ctx.scope == "volume":
            return True

        row_result = result(row)
        item_id = iid(row)
        segment_id = str(row_result.get("segment") or row.get("segment") or item_id or "")

        if ctx.scope == "segment":
            return segment_id == str(ctx.segment)

        chapter_value = row.get("chapter")
        if chapter_value is None and isinstance(row_result, dict):
            chapter_value = row_result.get("chapter")
        if chapter_value is not None:
            try:
                return int(chapter_value) == int(ctx.chapter)
            except Exception:
                pass
        if segment_id and segment_id in segment_to_chapter:
            return int(segment_to_chapter[segment_id]) == int(ctx.chapter)
        return False

    def _relevant_segment_ids(
        self,
        ctx: SelectionContext,
        segment_records: list[dict[str, Any]],
        *row_maps: dict[str, dict[str, Any]],
    ) -> list[str]:
        if ctx.scope == "segment":
            return [str(ctx.segment)]

        segment_ids = []
        for record in segment_records:
            segment_id = str(record.get("segment") or "")
            if not segment_id:
                continue
            if ctx.scope == "chapter":
                try:
                    if int(record.get("chapter", 0)) != int(ctx.chapter):
                        continue
                except Exception:
                    continue
            segment_ids.append(segment_id)

        for row_map in row_maps:
            for item_id in row_map:
                if item_id not in segment_ids:
                    if ctx.scope == "volume":
                        segment_ids.append(item_id)
                    elif ctx.scope == "chapter":
                        row = row_map.get(item_id) or {}
                        row_result = result(row)
                        chapter_value = row.get("chapter") or row_result.get("chapter")
                        if chapter_value is not None:
                            try:
                                if int(chapter_value) == int(ctx.chapter):
                                    segment_ids.append(item_id)
                            except Exception:
                                continue
        return segment_ids

    def _summarize_segment_glossary(self, row: dict[str, Any]) -> EditorRow:
        row_result = result(row)
        _field_name, entries = self.editor_actions.get_segment_glossary_entries(
            row_result if isinstance(row_result, dict) else {}
        )
        return EditorRow(
            values={
                "item_id": iid(row),
                "status": row.get("status", ""),
                "segment": row_result.get("segment") or iid(row),
                "terms_count": len(entries),
                "missing_count": len(row_result.get("missing_glossary_candidates") or []),
            },
            raw=row,
        )

    def _summarize_segment_pronouns(self, row: dict[str, Any]) -> EditorRow:
        row_result = result(row)
        _field_name, rules = self.editor_actions.get_segment_pronoun_rules(
            row_result if isinstance(row_result, dict) else {}
        )
        return EditorRow(
            values={
                "item_id": iid(row),
                "status": row.get("status", ""),
                "segment": row_result.get("segment") or iid(row),
                "rules_count": len(rules),
                "overrides_count": len(row_result.get("segment_override_candidates") or []),
                "missing_count": len(row_result.get("missing_rules") or []),
            },
            raw=row,
        )

    def _summarize_segment_context(self, row: dict[str, Any]) -> EditorRow:
        row_result = result(row)
        characters = row_result.get("characters") or row_result.get("participants") or row_result.get("named_characters") or []
        return EditorRow(
            values={
                "item_id": iid(row),
                "status": row.get("status", ""),
                "segment": row_result.get("segment", ""),
                "scene_type": row_result.get("scene_type", ""),
                "tone": row_result.get("tone") or row_result.get("overall_tone") or "",
                "characters_count": len(characters),
            },
            raw=row,
        )

    def _summarize_dialogue_labels(self, row: dict[str, Any]) -> EditorRow:
        row_result = result(row)
        summary = self.editor_actions.summarize_dialogue_labels(
            row_result if isinstance(row_result, dict) else {}
        )
        return EditorRow(
            values={
                "item_id": iid(row),
                "status": row.get("status", ""),
                "segment": row_result.get("segment") or iid(row),
                "units_count": summary["units_count"],
                "review_count": summary["review_count"],
                "low_confidence_count": summary["low_confidence_count"],
                "labeled_source_preview": self._preview_text(row_result.get("labeled_source", "")),
            },
            raw=row,
        )

    def _preview_text(self, text: Any, limit: int = 120) -> str:
        value = "" if text is None else str(text).replace("\n", " ").strip()
        if len(value) <= limit:
            return value
        return value[: max(0, limit - 3)] + "..."
