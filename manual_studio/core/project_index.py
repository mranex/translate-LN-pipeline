from __future__ import annotations

import re
from typing import Any

from .jsonio import item_id_from_record
from .workspace import Workspace


class ProjectIndex:
    VOLUME_RE = re.compile(r"^volume_(\d+)\.json$")

    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def list_volumes(self) -> list[int]:
        source_dir = self.workspace.p("source")
        if not source_dir.exists():
            return []
        volumes: list[int] = []
        for path in sorted(source_dir.glob("volume_*.json")):
            match = self.VOLUME_RE.match(path.name)
            if match:
                volumes.append(int(match.group(1)))
        return volumes

    def list_chapters(self, volume: int) -> list[str]:
        return [item_id_from_record(record) for record in self.get_chapter_records(volume)]

    def list_segments(self, volume: int) -> list[str]:
        return [str(record.get("segment") or item_id_from_record(record)) for record in self.get_segment_records(volume)]

    def get_segment_records(self, volume: int) -> list[dict[str, Any]]:
        return list(self.workspace.segments(volume))

    def get_chapter_records(self, volume: int) -> list[dict[str, Any]]:
        return list(self.workspace.chapters(volume))
