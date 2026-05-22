from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifact_store import ArtifactStore
from .jsonio import iid, read_json, read_jsonl, result
from .project_index import ProjectIndex
from .workspace import Workspace


@dataclass(frozen=True)
class EditResult:
    artifact: str
    path: str | None
    wrote: bool
    message: str


@dataclass(frozen=True)
class SegmentEditLoadResult:
    item_id: str
    path: str
    row: dict[str, Any]
    result: dict[str, Any]
    exists: bool
    message: str = ""


@dataclass(frozen=True)
class TranslationBundle:
    item_id: str
    volume: int
    segment_id: str
    source_record: dict[str, Any] | None
    dialogue_labels: dict[str, Any] | None
    segment_glossary: dict[str, Any] | None
    segment_pronouns: dict[str, Any] | None
    segment_context: dict[str, Any] | None
    draft_row: dict[str, Any] | None
    draft_result: dict[str, Any] | None
    fixed_row: dict[str, Any] | None
    fixed_result: dict[str, Any] | None
    qa_row: dict[str, Any] | None
    qa_result: dict[str, Any] | None


@dataclass(frozen=True)
class TranslationTextRef:
    field_name: str
    text: str


class EditorActionService:
    _DEFAULT_GLOSSARY_ROW = {
        "id": "",
        "source": "",
        "vi": "",
        "type": "other",
        "status": "tentative",
        "aliases": [],
        "variants": [],
        "forbidden_translations": [],
        "notes": "",
        "appears_in": [],
        "needs_human_review": True,
    }
    _DEFAULT_RELATIONSHIP_ROW = {
        "id": "",
        "speaker": "",
        "listener": "",
        "relationship": "",
        "self": "",
        "other": "",
        "scope": "volume_default",
        "status": "tentative",
        "variants": [],
        "notes": "",
        "needs_human_review": True,
    }
    _DEFAULT_SEGMENT_PRONOUN_RULE = {
        "id": "",
        "speaker": "",
        "listener": "",
        "relationship": "",
        "self": "",
        "other": "",
        "scope": "segment_override",
        "status": "tentative",
        "source": "manual_editor",
        "confidence": None,
        "notes": "",
        "needs_human_review": True,
    }
    _DEFAULT_DIALOGUE_UNIT = {
        "unit_id": "",
        "speaker": "UNKNOWN",
        "listener": "UNKNOWN",
        "source_text": "",
        "confidence": None,
        "review_required": True,
        "reason": "",
        "notes": "",
    }
    _TRANSLATION_TEXT_FIELDS = ("fixed_translation", "translation", "translated_text", "text")

    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.artifact_store = ArtifactStore(workspace)
        self.project_index = ProjectIndex(workspace)

    def load_volume_glossary(self, volume: int) -> dict[str, Any]:
        default = {"volume": volume, "volume_merge_glossary": [], "review_notes": []}
        return self._load_dict(
            draft_path=self.workspace.glossary_draft(volume),
            final_path=self.workspace.glossary_final(volume),
            default=default,
            artifact_name="volume glossary",
        )

    def save_volume_glossary_draft(self, volume: int, data: dict[str, Any]) -> EditResult:
        merged = self._merge_preserving_unknowns(self.load_volume_glossary(volume), data)
        merged["volume"] = volume
        merged.setdefault("review_notes", [])
        self._validate_glossary(merged)
        path = self.artifact_store.write_glossary_draft(volume, merged)
        return EditResult("volume_glossary", str(path), True, "Saved volume glossary draft.")

    def approve_volume_glossary(self, volume: int) -> EditResult:
        path = self.artifact_store.approve_glossary(volume)
        return EditResult("volume_glossary", str(path), True, "Approved volume glossary.")

    def load_volume_relationships(self, volume: int) -> dict[str, Any]:
        default = {"volume": volume, "relationship_pronoun_canon": [], "review_notes": []}
        return self._load_dict(
            draft_path=self.workspace.relationships_draft(volume),
            final_path=self.workspace.relationships_final(volume),
            default=default,
            artifact_name="volume relationships",
        )

    def save_volume_relationships_draft(self, volume: int, data: dict[str, Any]) -> EditResult:
        merged = self._merge_preserving_unknowns(self.load_volume_relationships(volume), data)
        merged["volume"] = volume
        merged.setdefault("review_notes", [])
        self._validate_relationships(merged)
        path = self.artifact_store.write_relationships_draft(volume, merged)
        return EditResult("volume_relationships", str(path), True, "Saved volume relationships draft.")

    def approve_volume_relationships(self, volume: int) -> EditResult:
        path = self.artifact_store.approve_relationships(volume)
        return EditResult("volume_relationships", str(path), True, "Approved volume relationships.")

    def load_segment_glossary(self, volume: int, segment_id: str) -> SegmentEditLoadResult:
        normalized_segment_id = self._ensure_segment_exists(volume, segment_id)
        path = self.workspace.segment_glossaries(volume)
        existing_row = self._find_jsonl_row(path, normalized_segment_id)
        if existing_row is None:
            default_result = self.default_segment_glossary_result()
            return SegmentEditLoadResult(
                item_id=normalized_segment_id,
                path=str(path),
                row={"item_id": normalized_segment_id, "status": "success", "result": copy.deepcopy(default_result)},
                result=default_result,
                exists=False,
                message="No existing segment glossary row was found. Editing an in-memory draft until save.",
            )

        row = copy.deepcopy(existing_row)
        row_result = result(row)
        resolved_result = copy.deepcopy(row_result if isinstance(row_result, dict) else {})
        self.get_segment_glossary_entries(resolved_result)
        return SegmentEditLoadResult(
            item_id=normalized_segment_id,
            path=str(path),
            row=row,
            result=resolved_result,
            exists=True,
        )

    def save_segment_glossary(self, volume: int, segment_id: str, result_obj: dict[str, Any]) -> EditResult:
        normalized_segment_id = self._ensure_segment_exists(volume, segment_id)
        if not isinstance(result_obj, dict):
            raise ValueError("Segment glossary result must be a JSON object.")
        self.get_segment_glossary_entries(result_obj)

        path = self.workspace.segment_glossaries(volume)
        wrapper_fields = self._existing_wrapper_fields(path, normalized_segment_id)
        self.artifact_store.upsert_jsonl(path, normalized_segment_id, copy.deepcopy(result_obj), wrapper_fields)
        return EditResult("segment_glossaries", str(path), True, "Saved segment glossary row.")

    def load_segment_pronouns(self, volume: int, segment_id: str) -> SegmentEditLoadResult:
        normalized_segment_id = self._ensure_segment_exists(volume, segment_id)
        path = self.workspace.segment_pronouns(volume)
        existing_row = self._find_jsonl_row(path, normalized_segment_id)
        if existing_row is None:
            default_result = self.default_segment_pronoun_result()
            return SegmentEditLoadResult(
                item_id=normalized_segment_id,
                path=str(path),
                row={"item_id": normalized_segment_id, "status": "success", "result": copy.deepcopy(default_result)},
                result=default_result,
                exists=False,
                message="No existing segment pronoun row was found. Editing an in-memory draft until save.",
            )

        row = copy.deepcopy(existing_row)
        row_result = result(row)
        resolved_result = copy.deepcopy(row_result if isinstance(row_result, dict) else {})
        self.get_segment_pronoun_rules(resolved_result)
        return SegmentEditLoadResult(
            item_id=normalized_segment_id,
            path=str(path),
            row=row,
            result=resolved_result,
            exists=True,
        )

    def save_segment_pronouns(self, volume: int, segment_id: str, result_obj: dict[str, Any]) -> EditResult:
        normalized_segment_id = self._ensure_segment_exists(volume, segment_id)
        if not isinstance(result_obj, dict):
            raise ValueError("Segment pronoun result must be a JSON object.")
        self.get_segment_pronoun_rules(result_obj)

        path = self.workspace.segment_pronouns(volume)
        wrapper_fields = self._existing_wrapper_fields(path, normalized_segment_id)
        self.artifact_store.upsert_jsonl(path, normalized_segment_id, copy.deepcopy(result_obj), wrapper_fields)
        return EditResult("segment_pronouns", str(path), True, "Saved segment pronoun row.")

    def load_dialogue_labels(self, volume: int, segment_id: str) -> SegmentEditLoadResult:
        record = self._segment_record(volume, segment_id)
        normalized_segment_id = str(record.get("segment"))
        path = self.workspace.dialogue_labels(volume)
        existing_row = self._find_jsonl_row(path, normalized_segment_id)
        if existing_row is None:
            default_result = self.default_dialogue_labels_result(volume, normalized_segment_id, record)
            return SegmentEditLoadResult(
                item_id=normalized_segment_id,
                path=str(path),
                row={"item_id": normalized_segment_id, "status": "success", "result": copy.deepcopy(default_result)},
                result=default_result,
                exists=False,
                message="No existing dialogue label row was found. Editing an in-memory draft until save.",
            )

        row = copy.deepcopy(existing_row)
        row_result = result(row)
        resolved_result = copy.deepcopy(row_result if isinstance(row_result, dict) else {})
        self.get_dialogue_units(resolved_result)
        return SegmentEditLoadResult(
            item_id=normalized_segment_id,
            path=str(path),
            row=row,
            result=resolved_result,
            exists=True,
        )

    def save_dialogue_labels(self, volume: int, segment_id: str, result_obj: dict[str, Any]) -> EditResult:
        normalized_segment_id = self._ensure_segment_exists(volume, segment_id)
        if not isinstance(result_obj, dict):
            raise ValueError("Dialogue labels result must be a JSON object.")
        labeled_source = result_obj.get("labeled_source")
        if not isinstance(labeled_source, str):
            raise ValueError("Dialogue labels result must include a string at 'labeled_source'.")
        if "units" in result_obj and not isinstance(result_obj.get("units"), list):
            raise ValueError("Dialogue labels result must include a list at 'units' when that field is present.")

        path = self.workspace.dialogue_labels(volume)
        wrapper_fields = self._existing_wrapper_fields(path, normalized_segment_id)
        self.artifact_store.upsert_jsonl(path, normalized_segment_id, copy.deepcopy(result_obj), wrapper_fields)
        return EditResult("dialogue_labels", str(path), True, "Saved dialogue labels row.")

    def load_translation_bundle(self, volume: int, segment_id: str) -> TranslationBundle:
        source_record = copy.deepcopy(self._segment_record(volume, segment_id))
        normalized_segment_id = str(source_record.get("segment") or segment_id)

        segment_glossary_row = self._find_jsonl_row(self.workspace.segment_glossaries(volume), normalized_segment_id)
        segment_pronouns_row = self._find_jsonl_row(self.workspace.segment_pronouns(volume), normalized_segment_id)
        segment_context_row = self._find_jsonl_row(self.workspace.segment_contexts(volume), normalized_segment_id)
        dialogue_labels_row = self._find_jsonl_row(self.workspace.dialogue_labels(volume), normalized_segment_id)
        draft_row = self._find_jsonl_row(self.workspace.draft_translations(volume), normalized_segment_id)
        fixed_row = self._find_jsonl_row(self.workspace.fixed_translations(volume), normalized_segment_id)
        qa_row = self._find_jsonl_row(self.workspace.qa_reports(volume), normalized_segment_id)

        draft_result = self._translation_result_or_default(
            draft_row,
            self.default_draft_translation_result(),
        )
        fixed_result = self._translation_result_or_default(
            fixed_row,
            copy.deepcopy(draft_result) if draft_row is not None else self.default_fixed_translation_result(),
        )

        return TranslationBundle(
            item_id=normalized_segment_id,
            volume=volume,
            segment_id=normalized_segment_id,
            source_record=source_record,
            dialogue_labels=self._row_result_dict(dialogue_labels_row),
            segment_glossary=self._row_result_dict(segment_glossary_row),
            segment_pronouns=self._row_result_dict(segment_pronouns_row),
            segment_context=self._row_result_dict(segment_context_row),
            draft_row=copy.deepcopy(draft_row) if isinstance(draft_row, dict) else None,
            draft_result=draft_result,
            fixed_row=copy.deepcopy(fixed_row) if isinstance(fixed_row, dict) else None,
            fixed_result=fixed_result,
            qa_row=copy.deepcopy(qa_row) if isinstance(qa_row, dict) else None,
            qa_result=self._row_result_dict(qa_row),
        )

    def get_translation_text(self, result_obj: dict[str, Any] | None) -> TranslationTextRef:
        if not isinstance(result_obj, dict):
            return TranslationTextRef("translation", "")
        for field_name in self._TRANSLATION_TEXT_FIELDS:
            if field_name in result_obj:
                value = result_obj.get(field_name)
                return TranslationTextRef(field_name, value if isinstance(value, str) else "")
        return TranslationTextRef("translation", "")

    def set_translation_text(
        self,
        result_obj: dict[str, Any],
        text: str,
        preferred_field: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(result_obj, dict):
            raise ValueError("Translation result must be a JSON object.")
        updated = copy.deepcopy(result_obj)
        field_name = None
        for candidate in self._translation_field_candidates(preferred_field):
            if candidate in updated:
                field_name = candidate
                break
        if field_name is None:
            field_name = preferred_field or "translation"
        updated[field_name] = text
        return updated

    def save_draft_translation(self, volume: int, segment_id: str, result_obj: dict[str, Any]) -> EditResult:
        normalized_segment_id = self._ensure_segment_exists(volume, segment_id)
        prepared = self._validate_translation_result(result_obj, preferred_field="translation")
        path = self.workspace.draft_translations(volume)
        wrapper_fields = self._existing_wrapper_fields(path, normalized_segment_id)
        self.artifact_store.upsert_jsonl(path, normalized_segment_id, prepared, wrapper_fields)
        return EditResult("draft_translations", str(path), True, "Saved draft translation row.")

    def save_fixed_translation(self, volume: int, segment_id: str, result_obj: dict[str, Any]) -> EditResult:
        normalized_segment_id = self._ensure_segment_exists(volume, segment_id)
        prepared = self._validate_translation_result(result_obj, preferred_field="fixed_translation")
        path = self.workspace.fixed_translations(volume)
        wrapper_fields = self._existing_wrapper_fields(path, normalized_segment_id)
        self.artifact_store.upsert_jsonl(path, normalized_segment_id, prepared, wrapper_fields)
        return EditResult("fixed_translations", str(path), True, "Saved fixed translation row.")

    def default_volume_glossary_row(self) -> dict[str, Any]:
        return copy.deepcopy(self._DEFAULT_GLOSSARY_ROW)

    def default_volume_relationship_row(self) -> dict[str, Any]:
        return copy.deepcopy(self._DEFAULT_RELATIONSHIP_ROW)

    def default_segment_glossary_result(self) -> dict[str, Any]:
        return {
            "segment_glossary": [],
            "missing_glossary_candidates": [],
            "notes": [],
        }

    def default_segment_glossary_entry(self) -> dict[str, Any]:
        return copy.deepcopy(self._DEFAULT_GLOSSARY_ROW)

    def default_segment_pronoun_result(self) -> dict[str, Any]:
        return {
            "segment_pronoun_table": [],
            "missing_rules": [],
            "notes": [],
        }

    def default_segment_pronoun_rule(self) -> dict[str, Any]:
        return copy.deepcopy(self._DEFAULT_SEGMENT_PRONOUN_RULE)

    def default_dialogue_labels_result(
        self,
        volume: int,
        segment_id: str,
        record: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        segment_record = record or self._segment_record(volume, segment_id)
        return {
            "item_id": str(segment_record.get("segment") or segment_id),
            "volume": volume,
            "chapter": segment_record.get("chapter"),
            "segment": str(segment_record.get("segment") or segment_id),
            "labeled_source": str(segment_record.get("content") or ""),
            "units": [],
        }

    def default_dialogue_unit(self) -> dict[str, Any]:
        return copy.deepcopy(self._DEFAULT_DIALOGUE_UNIT)

    def default_draft_translation_result(self) -> dict[str, Any]:
        return {
            "translation": "",
            "translator_notes": [],
        }

    def default_fixed_translation_result(self) -> dict[str, Any]:
        return {
            "fixed_translation": "",
        }

    def get_segment_glossary_entries(self, result_obj: dict[str, Any]) -> tuple[str, list[Any]]:
        if not isinstance(result_obj, dict):
            raise ValueError("Segment glossary result must be a JSON object.")
        entries = result_obj.get("segment_glossary")
        if entries is None:
            result_obj["segment_glossary"] = []
            entries = result_obj["segment_glossary"]
        if not isinstance(entries, list):
            raise ValueError("Segment glossary result must include a list at 'segment_glossary'.")
        return "segment_glossary", entries

    def get_segment_pronoun_rules(self, result_obj: dict[str, Any]) -> tuple[str, list[Any]]:
        if not isinstance(result_obj, dict):
            raise ValueError("Segment pronoun result must be a JSON object.")
        for key in ("segment_pronoun_table", "pronoun_rules", "rules"):
            value = result_obj.get(key)
            if isinstance(value, list):
                return key, value
        if "segment_pronoun_table" not in result_obj:
            result_obj["segment_pronoun_table"] = []
        value = result_obj.get("segment_pronoun_table")
        if not isinstance(value, list):
            raise ValueError(
                "Segment pronoun result must include a list at 'segment_pronoun_table', 'pronoun_rules', or 'rules'."
            )
        return "segment_pronoun_table", value

    def get_dialogue_units(self, result_obj: dict[str, Any]) -> tuple[str, list[Any]]:
        if not isinstance(result_obj, dict):
            raise ValueError("Dialogue labels result must be a JSON object.")
        units = result_obj.get("units")
        if units is None:
            result_obj["units"] = []
            units = result_obj["units"]
        if not isinstance(units, list):
            raise ValueError("Dialogue labels result must include a list at 'units' when that field is present.")
        return "units", units

    def summarize_dialogue_labels(self, result_obj: dict[str, Any]) -> dict[str, int]:
        units = [unit for unit in self.get_dialogue_units(result_obj)[1] if isinstance(unit, dict)]
        review_count = sum(1 for unit in units if unit.get("review_required") is True)
        low_confidence_count = sum(
            1 for unit in units if isinstance(unit.get("confidence"), (int, float)) and unit.get("confidence") < 0.8
        )
        return {
            "units_count": len(units),
            "review_count": review_count,
            "low_confidence_count": low_confidence_count,
        }

    def get_segment_source(self, volume: int, segment_id: str) -> str:
        return str(self._segment_record(volume, segment_id).get("content") or "")

    def summarize_translation(self, result_obj: dict[str, Any] | None) -> str:
        return self.get_translation_text(result_obj).text

    def _load_dict(self, draft_path, final_path, default: dict[str, Any], artifact_name: str) -> dict[str, Any]:
        data = read_json(draft_path, None)
        if data is None:
            data = read_json(final_path, None)
        if data is None:
            return copy.deepcopy(default)
        if not isinstance(data, dict):
            raise ValueError(f"The {artifact_name} artifact must contain a top-level JSON object.")
        merged = copy.deepcopy(default)
        for key, value in data.items():
            merged[key] = copy.deepcopy(value)
        return merged

    def _merge_preserving_unknowns(self, existing: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError("Edited artifact data must be a JSON object.")
        merged = copy.deepcopy(existing)
        for key, value in data.items():
            merged[key] = copy.deepcopy(value)
        return merged

    def _validate_glossary(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValueError("Volume glossary data must be a JSON object.")
        if not isinstance(data.get("volume_merge_glossary"), list):
            raise ValueError("Volume glossary data must include a list at 'volume_merge_glossary'.")

    def _validate_relationships(self, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValueError("Volume relationships data must be a JSON object.")
        if not isinstance(data.get("relationship_pronoun_canon"), list):
            raise ValueError("Volume relationships data must include a list at 'relationship_pronoun_canon'.")

    def _ensure_segment_exists(self, volume: int, segment_id: str) -> str:
        return str(self._segment_record(volume, segment_id).get("segment") or segment_id)

    def _segment_record(self, volume: int, segment_id: str) -> dict[str, Any]:
        target = str(segment_id)
        for record in self.project_index.get_segment_records(volume):
            if str(record.get("segment")) == target:
                return record
        raise ValueError(f"Segment '{segment_id}' was not found in volume {volume}.")

    def _find_jsonl_row(self, path: Path, item_id: str) -> dict[str, Any] | None:
        for row in read_jsonl(path):
            if isinstance(row, dict) and iid(row) == item_id:
                return row
        return None

    def _row_result_dict(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        row_result = result(row)
        return copy.deepcopy(row_result if isinstance(row_result, dict) else {})

    def _translation_result_or_default(
        self,
        row: dict[str, Any] | None,
        default: dict[str, Any],
    ) -> dict[str, Any]:
        row_result = self._row_result_dict(row)
        return row_result if row_result is not None else copy.deepcopy(default)

    def _translation_field_candidates(self, preferred_field: str | None = None) -> list[str]:
        ordered = []
        if preferred_field:
            ordered.append(preferred_field)
        for field_name in self._TRANSLATION_TEXT_FIELDS:
            if field_name not in ordered:
                ordered.append(field_name)
        return ordered

    def _validate_translation_result(
        self,
        result_obj: dict[str, Any],
        preferred_field: str,
    ) -> dict[str, Any]:
        if not isinstance(result_obj, dict):
            raise ValueError("Translation result must be a JSON object.")
        prepared = copy.deepcopy(result_obj)
        detected = self.get_translation_text(prepared)
        field_name = detected.field_name if detected.field_name in prepared else preferred_field
        value = prepared.get(field_name)
        if not isinstance(value, str):
            raise ValueError(f"Translation result must include a string at '{field_name}'.")
        return prepared

    def _existing_wrapper_fields(self, path: Path, item_id: str) -> dict[str, Any] | None:
        row = self._find_jsonl_row(path, item_id)
        if row is None:
            return None
        return {
            key: copy.deepcopy(value)
            for key, value in row.items()
            if key not in {"item_id", "status", "result"}
        }
