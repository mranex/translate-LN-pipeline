from __future__ import annotations

from pathlib import Path
from typing import Any

from .jsonio import iid, read_json, read_jsonl, write_json


class Workspace:
    """Project-scoped workspace rooted at ``data/<project_name>``."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    @classmethod
    def from_legacy(cls, repo_root: str | Path, project_name: str) -> "Workspace":
        return cls(Path(repo_root).joinpath("data", project_name))

    def p(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def config_path(self) -> Path:
        return self.p("project_config.json")

    def load_config(self) -> dict[str, Any]:
        return read_json(
            self.config_path(),
            {"name": self.root.name, "genre": "", "level": "Heavy", "enabled_steps": []},
        )

    def save_config(self, config: dict[str, Any]) -> None:
        write_json(self.config_path(), config)

    @property
    def prompts_root(self) -> Path:
        candidates = [
            self.root.joinpath("prompts"),
            self.root.parent.joinpath("prompts"),
            self.root.parent.parent.joinpath("prompts"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[-1]

    def source(self, volume: int) -> Path:
        return self.p("source", f"volume_{volume:02d}.json")

    def segments_file(self, volume: int) -> Path:
        return self.p("segments", f"volume_{volume:02d}.segments.json")

    def chapters(self, volume: int) -> list[Any]:
        data = read_json(self.source(volume), [])
        return data.get("chapters", []) if isinstance(data, dict) else data

    def segments(self, volume: int) -> list[Any]:
        data = read_json(self.segments_file(volume), [])
        return data.get("segments", []) if isinstance(data, dict) else data

    def glossary_draft(self, volume: int) -> Path:
        return self.p("canon", "glossary", "drafts", f"volume_{volume:02d}.glossary.draft.json")

    def glossary_final(self, volume: int) -> Path:
        return self.p("canon", "glossary", "finalized", f"volume_{volume:02d}.glossary.json")

    def series_glossary(self) -> Path:
        return self.p("canon", "series", "glossary.series.json")

    def active_volume_glossary(self, volume: int) -> Path:
        return self.p("canon", "glossary", "active", f"volume_{volume:02d}.glossary.active.json")

    def relationships_draft(self, volume: int) -> Path:
        return self.p("canon", "relationships", "drafts", f"volume_{volume:02d}.relationships.draft.json")

    def relationships_final(self, volume: int) -> Path:
        return self.p("canon", "relationships", "finalized", f"volume_{volume:02d}.relationships.json")

    def series_relationships(self) -> Path:
        return self.p("canon", "series", "relationships.series.json")

    def active_volume_relationships(self, volume: int) -> Path:
        return self.p(
            "canon",
            "relationships",
            "active",
            f"volume_{volume:02d}.relationships.active.json",
        )

    def series_glossary_sync_report(self, volume: int) -> Path:
        return self.p("canon", "series", "logs", f"volume_{volume:02d}.glossary_sync_report.json")

    def series_relationships_sync_report(self, volume: int) -> Path:
        return self.p("canon", "series", "logs", f"volume_{volume:02d}.relationships_sync_report.json")

    def glossary_extractions(self, volume: int) -> Path:
        return self.p("working", "glossary_extractions", f"volume_{volume:02d}.glossary_extractions.jsonl")

    def relationship_extractions(self, volume: int) -> Path:
        return self.p(
            "working",
            "relationship_extractions",
            f"volume_{volume:02d}.relationships_extractions.jsonl",
        )

    def segment_glossaries(self, volume: int) -> Path:
        return self.p("working", "segment_glossaries", f"volume_{volume:02d}.segment_glossaries.jsonl")

    def segment_pronouns(self, volume: int) -> Path:
        return self.p("canon", "segment_pronouns", f"volume_{volume:02d}.segment_pronouns.jsonl")

    def segment_contexts(self, volume: int) -> Path:
        return self.p("working", "segment_contexts", f"volume_{volume:02d}.segment_contexts.jsonl")

    def dialogue_labels(self, volume: int) -> Path:
        return self.p("working", "dialogue_labels", f"volume_{volume:02d}.dialogue_labels.jsonl")

    def draft_translations(self, volume: int) -> Path:
        return self.p("working", "translations", "draft", f"volume_{volume:02d}.translated.jsonl")

    def qa_reports(self, volume: int) -> Path:
        return self.p("working", "translations", "qa", f"volume_{volume:02d}.qa.jsonl")

    def fixed_translations(self, volume: int) -> Path:
        return self.p("working", "translations", "fixed", f"volume_{volume:02d}.fixed.jsonl")

    def release_json(self, volume: int) -> Path:
        return self.p("release", f"volume_{volume:02d}.vi.json")

    def release_md(self, volume: int) -> Path:
        return self.p("release", f"volume_{volume:02d}.vi.md")

    def map_jsonl(self, path: str | Path) -> dict[str, Any]:
        return {iid(row): row for row in read_jsonl(Path(path))}

    # Compatibility aliases for the current WS class.
    def segs(self, volume: int) -> Path:
        return self.segments_file(volume)

    def g_draft(self, volume: int) -> Path:
        return self.glossary_draft(volume)

    def g_final(self, volume: int) -> Path:
        return self.glossary_final(volume)

    def r_draft(self, volume: int) -> Path:
        return self.relationships_draft(volume)

    def r_final(self, volume: int) -> Path:
        return self.relationships_final(volume)

    def ge(self, volume: int) -> Path:
        return self.glossary_extractions(volume)

    def re(self, volume: int) -> Path:
        return self.relationship_extractions(volume)

    def sg(self, volume: int) -> Path:
        return self.segment_glossaries(volume)

    def sp(self, volume: int) -> Path:
        return self.segment_pronouns(volume)

    def sc(self, volume: int) -> Path:
        return self.segment_contexts(volume)

    def dl(self, volume: int) -> Path:
        return self.dialogue_labels(volume)

    def tr(self, volume: int) -> Path:
        return self.draft_translations(volume)

    def qa(self, volume: int) -> Path:
        return self.qa_reports(volume)

    def fx(self, volume: int) -> Path:
        return self.fixed_translations(volume)

    def rel_json(self, volume: int) -> Path:
        return self.release_json(volume)

    def rel_md(self, volume: int) -> Path:
        return self.release_md(volume)
