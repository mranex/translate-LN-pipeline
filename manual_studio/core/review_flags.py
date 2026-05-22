from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .jsonio import result
from .project_index import ProjectIndex
from .workspace import Workspace


@dataclass(frozen=True)
class ReviewFlag:
    severity: str
    source: str
    item_id: str
    message: str
    payload: dict[str, Any] | None


class ReviewFlagService:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.index = ProjectIndex(workspace)

    def flags_for_volume(self, volume: int) -> list[ReviewFlag]:
        flags: list[ReviewFlag] = []
        for segment_id in self.index.list_segments(volume):
            flags.extend(self.flags_for_segment(volume, segment_id))
        return flags

    def flags_for_segment(self, volume: int, segment_id: str) -> list[ReviewFlag]:
        item_id = str(segment_id)
        flags: list[ReviewFlag] = []

        glossary_row = self._success_row(self.workspace.segment_glossaries(volume), item_id)
        if glossary_row is not None:
            glossary_result = result(glossary_row)
            missing_candidates = glossary_result.get("missing_glossary_candidates") or []
            if missing_candidates:
                flags.append(
                    ReviewFlag(
                        severity="warning",
                        source="segment_glossary",
                        item_id=item_id,
                        message="Segment glossary has missing glossary candidates.",
                        payload={"missing_glossary_candidates": missing_candidates},
                    )
                )

        pronoun_row = self._success_row(self.workspace.segment_pronouns(volume), item_id)
        if pronoun_row is not None:
            pronoun_result = result(pronoun_row)
            missing_rules = pronoun_result.get("missing_rules") or []
            if missing_rules:
                flags.append(
                    ReviewFlag(
                        severity="warning",
                        source="segment_pronouns",
                        item_id=item_id,
                        message="Segment pronouns have missing rules.",
                        payload={"missing_rules": missing_rules},
                    )
                )

        dialogue_row = self._success_row(self.workspace.dialogue_labels(volume), item_id)
        if dialogue_row is not None:
            flags.extend(self._dialogue_flags(item_id, result(dialogue_row)))

        translation_row = self._success_row(self.workspace.fixed_translations(volume), item_id)
        if translation_row is None:
            translation_row = self._success_row(self.workspace.draft_translations(volume), item_id)
        if translation_row is not None:
            flags.extend(self._translation_flags(item_id, result(translation_row)))

        return flags

    def _success_row(self, path, item_id: str) -> dict[str, Any] | None:
        row = self.workspace.map_jsonl(path).get(item_id)
        if isinstance(row, dict) and row.get("status") == "success":
            return row
        return None

    def _dialogue_flags(self, item_id: str, dialogue_result: dict[str, Any]) -> list[ReviewFlag]:
        flags: list[ReviewFlag] = []
        units = [unit for unit in dialogue_result.get("units", []) if isinstance(unit, dict)]
        review_required = [unit for unit in units if unit.get("review_required") is True]
        if review_required:
            flags.append(
                ReviewFlag(
                    severity="warning",
                    source="dialogue_labels",
                    item_id=item_id,
                    message="Dialogue labels contain units marked for review.",
                    payload={"units": review_required},
                )
            )

        low_confidence_units = []
        for unit in units:
            confidence = unit.get("confidence")
            if isinstance(confidence, (int, float)) and confidence < 0.8:
                low_confidence_units.append(unit)
        top_level_confidence = dialogue_result.get("confidence")
        if isinstance(top_level_confidence, (int, float)) and top_level_confidence < 0.8:
            low_confidence_units.append({"confidence": top_level_confidence})
        if low_confidence_units:
            flags.append(
                ReviewFlag(
                    severity="warning",
                    source="dialogue_labels",
                    item_id=item_id,
                    message="Dialogue labels contain low-confidence output.",
                    payload={"units": low_confidence_units},
                )
            )
        return flags

    def _translation_flags(self, item_id: str, translation_result: dict[str, Any]) -> list[ReviewFlag]:
        flags: list[ReviewFlag] = []
        for field_name in ("warnings", "issues"):
            value = translation_result.get(field_name)
            if self._has_value(value):
                flags.append(
                    ReviewFlag(
                        severity="warning",
                        source="translation",
                        item_id=item_id,
                        message=f"Translation result includes {field_name}.",
                        payload={field_name: value},
                    )
                )
        return flags

    def _has_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, (list, dict, str)):
            return bool(value)
        return True
