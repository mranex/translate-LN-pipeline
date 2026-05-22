from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .jsonio import backup, iid, read_json, read_jsonl, write_json, write_jsonl
from .workspace import Workspace


class ArtifactStore:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def upsert_jsonl(
        self,
        path: str | Path,
        item_id: str,
        obj: dict[str, Any],
        wrapper_fields: dict[str, Any] | None = None,
    ) -> None:
        target = Path(path)
        rows = read_jsonl(target)
        row = dict(wrapper_fields or {})
        row.update({"item_id": item_id, "status": "success", "result": obj})
        found = False
        for index, existing in enumerate(rows):
            if iid(existing) == item_id:
                rows[index] = row
                found = True
                break
        if not found:
            rows.append(row)
        backup(target)
        write_jsonl(target, rows)

    def load_glossary(self, volume: int) -> dict[str, Any]:
        default = {"volume": volume, "volume_merge_glossary": [], "review_notes": []}
        return read_json(self.workspace.glossary_draft(volume), None) or read_json(
            self.workspace.glossary_final(volume),
            default,
        )

    def load_relationships(self, volume: int) -> dict[str, Any]:
        default = {"volume": volume, "relationship_pronoun_canon": [], "review_notes": []}
        return read_json(self.workspace.relationships_draft(volume), None) or read_json(
            self.workspace.relationships_final(volume),
            default,
        )

    def approve_glossary(self, volume: int) -> Path:
        return self._approve(
            self.workspace.glossary_draft(volume),
            self.workspace.glossary_final(volume),
        )

    def approve_relationships(self, volume: int) -> Path:
        return self._approve(
            self.workspace.relationships_draft(volume),
            self.workspace.relationships_final(volume),
        )

    def write_glossary_draft(self, volume: int, obj: dict[str, Any]) -> Path:
        path = self.workspace.glossary_draft(volume)
        backup(path)
        write_json(path, obj)
        return path

    def write_relationships_draft(self, volume: int, obj: dict[str, Any]) -> Path:
        path = self.workspace.relationships_draft(volume)
        backup(path)
        write_json(path, obj)
        return path

    def _approve(self, src: Path, dst: Path) -> Path:
        if not src.exists():
            raise FileNotFoundError(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        backup(dst)
        shutil.copy2(src, dst)
        return dst
