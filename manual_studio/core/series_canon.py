from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .jsonio import backup, read_json, write_json
from .workspace import Workspace


@dataclass(frozen=True)
class SeriesActionResult:
    artifact: str
    path: Path | None
    wrote: bool
    message: str
    added_count: int = 0
    skipped_count: int = 0
    conflict_count: int = 0
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class ActiveCanonResult:
    volume: int
    path: Path | None
    wrote: bool
    matched_count: int
    total_series_entries: int
    message: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class SyncReport:
    volume: int
    artifact: str
    added: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    ambiguous: list[dict[str, Any]]
    messages: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "volume": self.volume,
            "artifact": self.artifact,
            "added": copy.deepcopy(self.added),
            "skipped": copy.deepcopy(self.skipped),
            "conflicts": copy.deepcopy(self.conflicts),
            "ambiguous": copy.deepcopy(self.ambiguous),
            "messages": copy.deepcopy(self.messages),
        }


class SeriesCanonService:
    _ACTIVE_CHARACTER_TYPES = {"character", "alias", "title", "epithet"}
    _SPECIAL_RELATIONSHIP_TOKENS = {"UNKNOWN", "GROUP", "self", "SELF"}

    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def default_series_glossary(self) -> dict[str, Any]:
        return {
            "volume": 0,
            "volume_merge_glossary": [],
            "review_notes": [],
        }

    def load_series_glossary(self) -> dict[str, Any]:
        return self._load_object(
            self.workspace.series_glossary(),
            self.default_series_glossary(),
            "volume_merge_glossary",
            "series glossary",
        )

    def save_series_glossary(self, data: dict[str, Any]) -> SeriesActionResult:
        saved = self._save_object(
            data,
            self.load_series_glossary(),
            self.workspace.series_glossary(),
            "volume_merge_glossary",
            "series_glossary",
            "series glossary",
        )
        return SeriesActionResult(
            artifact="series_glossary",
            path=self.workspace.series_glossary(),
            wrote=True,
            message="Saved series glossary.",
            payload=saved,
        )

    def initialize_series_glossary_from_volume(self, volume: int) -> SeriesActionResult:
        path = self.workspace.glossary_final(volume)
        obj = read_json(path, None)
        if obj is None:
            return SeriesActionResult(
                artifact="series_glossary",
                path=None,
                wrote=False,
                message=f"Missing finalized glossary: {path}",
            )

        prepared = self._normalize_loaded_object(
            obj,
            self.default_series_glossary(),
            "volume_merge_glossary",
            "finalized volume glossary",
        )
        prepared["volume"] = 0
        self._write_json(self.workspace.series_glossary(), prepared)
        return SeriesActionResult(
            artifact="series_glossary",
            path=self.workspace.series_glossary(),
            wrote=True,
            message=f"Initialized series glossary from volume {volume}.",
            added_count=len(prepared.get("volume_merge_glossary") or []),
            payload=copy.deepcopy(prepared),
        )

    def build_active_volume_glossary(self, volume: int, write: bool = True) -> ActiveCanonResult:
        series_obj = self.load_series_glossary()
        source_text = self.build_volume_source_text(volume)
        series_entries = series_obj.get("volume_merge_glossary") or []

        matched_entries: list[dict[str, Any]] = []
        for entry in series_entries:
            if not isinstance(entry, dict):
                continue
            terms = self.glossary_entry_match_terms(entry)
            if any(term in source_text for term in terms):
                matched_entries.append(copy.deepcopy(entry))

        active_obj = {
            "volume": volume,
            "volume_merge_glossary": matched_entries,
            "review_notes": [],
        }
        path = self.workspace.active_volume_glossary(volume) if write else None
        if write:
            self._write_json(self.workspace.active_volume_glossary(volume), active_obj)

        return ActiveCanonResult(
            volume=volume,
            path=path,
            wrote=write,
            matched_count=len(matched_entries),
            total_series_entries=len(series_entries),
            message=f"Built active volume glossary with {len(matched_entries)} of {len(series_entries)} series entries matched.",
            payload=copy.deepcopy(active_obj),
        )

    def sync_volume_glossary_to_series(self, volume: int) -> SeriesActionResult:
        final_path = self.workspace.glossary_final(volume)
        final_obj = read_json(final_path, None)
        if final_obj is None:
            return SeriesActionResult(
                artifact="series_glossary_sync",
                path=None,
                wrote=False,
                message=f"Missing finalized glossary: {final_path}",
            )

        volume_obj = self._normalize_loaded_object(
            final_obj,
            self.default_series_glossary(),
            "volume_merge_glossary",
            "finalized volume glossary",
        )
        series_obj = self.load_series_glossary()
        series_entries = series_obj.get("volume_merge_glossary") or []

        added: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []

        for entry in volume_obj.get("volume_merge_glossary") or []:
            if not isinstance(entry, dict):
                conflicts.append(
                    {
                        "reason": "invalid_entry",
                        "volume_entry": copy.deepcopy(entry),
                    }
                )
                continue

            matches = [
                (index, candidate)
                for index, candidate in enumerate(series_entries)
                if isinstance(candidate, dict) and self.glossary_entries_overlap(entry, candidate)
            ]
            if not matches:
                series_entries.append(copy.deepcopy(entry))
                added.append(copy.deepcopy(entry))
                continue

            if len(matches) > 1:
                ambiguous.append(
                    {
                        "reason": "multiple_matches",
                        "volume_entry": copy.deepcopy(entry),
                        "series_matches": [copy.deepcopy(candidate) for _index, candidate in matches],
                    }
                )
                continue

            _index, candidate = matches[0]
            reasons = self._glossary_conflict_reasons(candidate, entry)
            if reasons:
                conflicts.append(
                    {
                        "reason": "meaningful_conflict",
                        "reasons": reasons,
                        "volume_entry": copy.deepcopy(entry),
                        "series_entry": copy.deepcopy(candidate),
                    }
                )
                continue

            skipped.append(
                {
                    "reason": "existing_match",
                    "volume_entry": copy.deepcopy(entry),
                    "series_entry": copy.deepcopy(candidate),
                }
            )

        messages = [
            f"Processed {len(volume_obj.get('volume_merge_glossary') or [])} finalized glossary entries.",
            f"Added {len(added)} new series glossary entries.",
            f"Skipped {len(skipped)} glossary entries with non-conflicting matches.",
            f"Logged {len(conflicts)} glossary conflicts.",
            f"Logged {len(ambiguous)} ambiguous glossary matches.",
        ]
        report = SyncReport(
            volume=volume,
            artifact="series_glossary",
            added=added,
            skipped=skipped,
            conflicts=conflicts,
            ambiguous=ambiguous,
            messages=messages,
        )

        if added:
            self._write_json(self.workspace.series_glossary(), series_obj)
        self._write_json(self.workspace.series_glossary_sync_report(volume), report.as_dict())

        return SeriesActionResult(
            artifact="series_glossary_sync",
            path=self.workspace.series_glossary_sync_report(volume),
            wrote=True,
            message=f"Synced finalized volume glossary into series glossary with {len(added)} additions.",
            added_count=len(added),
            skipped_count=len(skipped),
            conflict_count=len(conflicts) + len(ambiguous),
            payload=report.as_dict(),
        )

    def default_series_relationships(self) -> dict[str, Any]:
        return {
            "volume": 0,
            "relationship_pronoun_canon": [],
            "review_notes": [],
        }

    def load_series_relationships(self) -> dict[str, Any]:
        return self._load_object(
            self.workspace.series_relationships(),
            self.default_series_relationships(),
            "relationship_pronoun_canon",
            "series relationships",
        )

    def save_series_relationships(self, data: dict[str, Any]) -> SeriesActionResult:
        saved = self._save_object(
            data,
            self.load_series_relationships(),
            self.workspace.series_relationships(),
            "relationship_pronoun_canon",
            "series_relationships",
            "series relationships",
        )
        return SeriesActionResult(
            artifact="series_relationships",
            path=self.workspace.series_relationships(),
            wrote=True,
            message="Saved series relationships.",
            payload=saved,
        )

    def initialize_series_relationships_from_volume(self, volume: int) -> SeriesActionResult:
        path = self.workspace.relationships_final(volume)
        obj = read_json(path, None)
        if obj is None:
            return SeriesActionResult(
                artifact="series_relationships",
                path=None,
                wrote=False,
                message=f"Missing finalized relationships: {path}",
            )

        prepared = self._normalize_loaded_object(
            obj,
            self.default_series_relationships(),
            "relationship_pronoun_canon",
            "finalized volume relationships",
        )
        prepared["volume"] = 0
        self._write_json(self.workspace.series_relationships(), prepared)
        return SeriesActionResult(
            artifact="series_relationships",
            path=self.workspace.series_relationships(),
            wrote=True,
            message=f"Initialized series relationships from volume {volume}.",
            added_count=len(prepared.get("relationship_pronoun_canon") or []),
            payload=copy.deepcopy(prepared),
        )

    def build_active_volume_relationships(self, volume: int, write: bool = True) -> ActiveCanonResult:
        series_obj = self.load_series_relationships()
        active_glossary = self.build_active_volume_glossary(volume, write=False).payload
        active_tokens = self.active_character_tokens_from_glossary(active_glossary)
        series_entries = series_obj.get("relationship_pronoun_canon") or []

        matched_entries: list[dict[str, Any]] = []
        for entry in series_entries:
            if not isinstance(entry, dict):
                continue
            identity = self.relationship_identity(entry)
            if identity is None:
                continue
            speaker, listener = identity
            speaker_active = speaker in active_tokens
            listener_active = listener in active_tokens
            speaker_special = speaker in self._SPECIAL_RELATIONSHIP_TOKENS
            listener_special = listener in self._SPECIAL_RELATIONSHIP_TOKENS
            if (speaker_active and listener_active) or (speaker_active and listener_special) or (
                listener_active and speaker_special
            ):
                matched_entries.append(copy.deepcopy(entry))

        active_obj = {
            "volume": volume,
            "relationship_pronoun_canon": matched_entries,
            "review_notes": [],
        }
        path = self.workspace.active_volume_relationships(volume) if write else None
        if write:
            self._write_json(self.workspace.active_volume_relationships(volume), active_obj)

        return ActiveCanonResult(
            volume=volume,
            path=path,
            wrote=write,
            matched_count=len(matched_entries),
            total_series_entries=len(series_entries),
            message=f"Built active volume relationships with {len(matched_entries)} of {len(series_entries)} series entries matched.",
            payload=copy.deepcopy(active_obj),
        )

    def sync_volume_relationships_to_series(self, volume: int) -> SeriesActionResult:
        final_path = self.workspace.relationships_final(volume)
        final_obj = read_json(final_path, None)
        if final_obj is None:
            return SeriesActionResult(
                artifact="series_relationships_sync",
                path=None,
                wrote=False,
                message=f"Missing finalized relationships: {final_path}",
            )

        volume_obj = self._normalize_loaded_object(
            final_obj,
            self.default_series_relationships(),
            "relationship_pronoun_canon",
            "finalized volume relationships",
        )
        series_obj = self.load_series_relationships()
        series_entries = series_obj.get("relationship_pronoun_canon") or []

        added: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        ambiguous: list[dict[str, Any]] = []

        for entry in volume_obj.get("relationship_pronoun_canon") or []:
            if not isinstance(entry, dict):
                conflicts.append(
                    {
                        "reason": "invalid_entry",
                        "volume_entry": copy.deepcopy(entry),
                    }
                )
                continue

            identity = self.relationship_identity(entry)
            if identity is None:
                conflicts.append(
                    {
                        "reason": "missing_identity",
                        "volume_entry": copy.deepcopy(entry),
                    }
                )
                continue

            matches = [
                candidate
                for candidate in series_entries
                if isinstance(candidate, dict) and self.relationship_identity(candidate) == identity
            ]
            if not matches:
                series_entries.append(copy.deepcopy(entry))
                added.append(copy.deepcopy(entry))
                continue

            if len(matches) > 1:
                ambiguous.append(
                    {
                        "reason": "multiple_matches",
                        "identity": list(identity),
                        "volume_entry": copy.deepcopy(entry),
                        "series_matches": [copy.deepcopy(candidate) for candidate in matches],
                    }
                )
                continue

            candidate = matches[0]
            reasons = self._relationship_conflict_reasons(candidate, entry)
            if reasons:
                conflicts.append(
                    {
                        "reason": "meaningful_conflict",
                        "identity": list(identity),
                        "reasons": reasons,
                        "volume_entry": copy.deepcopy(entry),
                        "series_entry": copy.deepcopy(candidate),
                    }
                )
                continue

            skipped.append(
                {
                    "reason": "existing_match",
                    "identity": list(identity),
                    "volume_entry": copy.deepcopy(entry),
                    "series_entry": copy.deepcopy(candidate),
                }
            )

        messages = [
            f"Processed {len(volume_obj.get('relationship_pronoun_canon') or [])} finalized relationship entries.",
            f"Added {len(added)} new series relationship entries.",
            f"Skipped {len(skipped)} relationship entries with non-conflicting matches.",
            f"Logged {len(conflicts)} relationship conflicts.",
            f"Logged {len(ambiguous)} ambiguous relationship matches.",
        ]
        report = SyncReport(
            volume=volume,
            artifact="series_relationships",
            added=added,
            skipped=skipped,
            conflicts=conflicts,
            ambiguous=ambiguous,
            messages=messages,
        )

        if added:
            self._write_json(self.workspace.series_relationships(), series_obj)
        self._write_json(self.workspace.series_relationships_sync_report(volume), report.as_dict())

        return SeriesActionResult(
            artifact="series_relationships_sync",
            path=self.workspace.series_relationships_sync_report(volume),
            wrote=True,
            message=f"Synced finalized volume relationships into series relationships with {len(added)} additions.",
            added_count=len(added),
            skipped_count=len(skipped),
            conflict_count=len(conflicts) + len(ambiguous),
            payload=report.as_dict(),
        )

    def glossary_entry_match_terms(self, entry: dict[str, Any]) -> list[str]:
        if not isinstance(entry, dict):
            return []
        terms: list[str] = []
        self._append_term(terms, entry.get("source"))
        aliases = entry.get("aliases")
        if isinstance(aliases, list):
            for alias in aliases:
                self._append_term(terms, alias)
        return terms

    def glossary_entries_overlap(self, a: dict[str, Any], b: dict[str, Any]) -> bool:
        if not isinstance(a, dict) or not isinstance(b, dict):
            return False
        return bool(set(self.glossary_entry_match_terms(a)) & set(self.glossary_entry_match_terms(b)))

    def relationship_identity(self, entry: dict[str, Any]) -> tuple[str, str] | None:
        if not isinstance(entry, dict):
            return None
        speaker = entry.get("speaker")
        listener = entry.get("listener")
        if not isinstance(speaker, str) or not isinstance(listener, str):
            return None
        speaker = speaker.strip()
        listener = listener.strip()
        if not speaker or not listener:
            return None
        return speaker, listener

    def build_volume_source_text(self, volume: int) -> str:
        texts: list[str] = []
        seen: set[str] = set()
        for record in list(self.workspace.chapters(volume)) + list(self.workspace.segments(volume)):
            if not isinstance(record, dict):
                continue
            content = record.get("content")
            if not isinstance(content, str):
                continue
            content = content.strip()
            if not content or content in seen:
                continue
            seen.add(content)
            texts.append(content)
        return "\n\n".join(texts)

    def active_character_tokens_from_glossary(self, glossary_obj: dict[str, Any]) -> set[str]:
        if not isinstance(glossary_obj, dict):
            raise ValueError("Active glossary object must be a JSON object.")

        tokens: set[str] = set()
        entries = glossary_obj.get("volume_merge_glossary")
        if not isinstance(entries, list):
            raise ValueError("Active glossary object must include a list at 'volume_merge_glossary'.")

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") not in self._ACTIVE_CHARACTER_TYPES:
                continue
            for value in (entry.get("source"), entry.get("vi"), entry.get("id")):
                if isinstance(value, str) and value.strip():
                    tokens.add(value.strip())
            aliases = entry.get("aliases")
            if isinstance(aliases, list):
                for alias in aliases:
                    if isinstance(alias, str) and alias.strip():
                        tokens.add(alias.strip())
        return tokens

    def _load_object(
        self,
        path: Path,
        default: dict[str, Any],
        list_key: str,
        artifact_name: str,
    ) -> dict[str, Any]:
        obj = read_json(path, None)
        if obj is None:
            return copy.deepcopy(default)
        return self._normalize_loaded_object(obj, default, list_key, artifact_name)

    def _normalize_loaded_object(
        self,
        obj: Any,
        default: dict[str, Any],
        list_key: str,
        artifact_name: str,
    ) -> dict[str, Any]:
        if not isinstance(obj, dict):
            raise ValueError(f"The {artifact_name} artifact must contain a top-level JSON object.")
        merged = copy.deepcopy(default)
        for key, value in obj.items():
            merged[key] = copy.deepcopy(value)
        self._validate_list_key(merged, list_key, artifact_name)
        return merged

    def _save_object(
        self,
        data: dict[str, Any],
        existing: dict[str, Any],
        path: Path,
        list_key: str,
        artifact_id: str,
        artifact_name: str,
    ) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ValueError(f"{artifact_name.title()} data must be a JSON object.")
        merged = copy.deepcopy(existing)
        for key, value in data.items():
            merged[key] = copy.deepcopy(value)
        self._validate_list_key(merged, list_key, artifact_name)
        self._write_json(path, merged)
        return merged

    def _validate_list_key(self, data: dict[str, Any], list_key: str, artifact_name: str) -> None:
        value = data.get(list_key)
        if not isinstance(value, list):
            raise ValueError(f"{artifact_name.title()} data must include a list at '{list_key}'.")

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        backup(path)
        write_json(path, data)

    def _append_term(self, terms: list[str], value: Any) -> None:
        if not isinstance(value, str):
            return
        normalized = value.strip()
        if not normalized or normalized in terms:
            return
        terms.append(normalized)

    def _glossary_conflict_reasons(self, series_entry: dict[str, Any], volume_entry: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        series_vi = self._non_empty_string(series_entry.get("vi"))
        volume_vi = self._non_empty_string(volume_entry.get("vi"))
        if series_vi and volume_vi and series_vi != volume_vi:
            reasons.append("vi")

        series_type = self._non_empty_string(series_entry.get("type"))
        volume_type = self._non_empty_string(volume_entry.get("type"))
        if series_type and volume_type and series_type != volume_type:
            reasons.append("type")
        return reasons

    def _relationship_conflict_reasons(self, series_entry: dict[str, Any], volume_entry: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        for field_name in ("relationship", "self", "other"):
            series_value = self._non_empty_string(series_entry.get(field_name))
            volume_value = self._non_empty_string(volume_entry.get(field_name))
            if series_value and volume_value and series_value != volume_value:
                reasons.append(field_name)
        return reasons

    def _non_empty_string(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()
