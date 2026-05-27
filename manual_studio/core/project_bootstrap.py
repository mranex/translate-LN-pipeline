from __future__ import annotations

import re
from pathlib import Path

from .jsonio import write_json


LEVEL_STEPS: dict[str, list[str]] = {
    "Heavy": [
        "extract_chapter_glossary",
        "merge_volume_glossary",
        "review_volume_glossary",
        "extract_chapter_relationships",
        "merge_volume_relationships",
        "review_volume_relationships",
        "build_segment_glossary",
        "review_segment_glossary",
        "build_segment_pronouns",
        "review_segment_pronouns",
        "build_segment_context",
        "label_dialogue",
        "translate",
        "qa",
        "fix",
        "assemble",
    ],
    "Medium": [
        "extract_chapter_glossary",
        "merge_volume_glossary",
        "review_volume_glossary",
        "extract_chapter_relationships",
        "merge_volume_relationships",
        "review_volume_relationships",
        "label_dialogue",
        "translate",
        "assemble",
    ],
    "Lite": [
        "extract_chapter_glossary",
        "merge_volume_glossary",
        "review_volume_glossary",
        "extract_chapter_relationships",
        "merge_volume_relationships",
        "review_volume_relationships",
        "label_dialogue",
        "translate",
        "assemble",
    ],
}

PROJECT_SCAFFOLD_DIRS: tuple[str, ...] = (
    "source",
    "segments",
    "canon/glossary/drafts",
    "canon/glossary/finalized",
    "canon/glossary/active",
    "canon/relationships/drafts",
    "canon/relationships/finalized",
    "canon/relationships/active",
    "canon/series",
    "canon/series/logs",
    "canon/segment_pronouns",
    "working/glossary_extractions",
    "working/relationship_extractions",
    "working/segment_glossaries",
    "working/segment_contexts",
    "working/dialogue_labels",
    "working/translations/draft",
    "working/translations/qa",
    "working/translations/fixed",
    "release",
)

RESERVED_PROJECT_NAMES = frozenset({"source", "segments"})
INVALID_NAME_CHARS_RE = re.compile(r'[<>:"/\\|?*]')


class ProjectBootstrapError(ValueError):
    """Raised when a project cannot be created from the provided inputs."""


def build_project_config(name: str, genre: str, level: str) -> dict[str, object]:
    normalized_name = _validate_project_name(name)
    normalized_level = normalize_level(level)
    return {
        "name": normalized_name,
        "genre": genre.strip(),
        "level": normalized_level,
        "enabled_steps": list(LEVEL_STEPS[normalized_level]),
    }


def create_project(repo_root: str | Path, name: str, genre: str, level: str) -> Path:
    root = Path(repo_root).expanduser()
    if not root.exists() or not root.is_dir():
        raise ProjectBootstrapError("Repo root does not exist or is not a directory.")

    project_name = _validate_project_name(name)
    project_root = root.joinpath("data", project_name)
    if project_root.exists():
        raise ProjectBootstrapError(f"Project already exists: {project_name}")

    config = build_project_config(project_name, genre, level)
    project_root.mkdir(parents=True, exist_ok=False)
    for relative_dir in PROJECT_SCAFFOLD_DIRS:
        project_root.joinpath(relative_dir).mkdir(parents=True, exist_ok=True)

    write_json(project_root.joinpath("project_config.json"), config)
    return project_root


def normalize_level(level: str) -> str:
    normalized = level.strip()
    if normalized not in LEVEL_STEPS:
        supported = ", ".join(LEVEL_STEPS)
        raise ProjectBootstrapError(f"Unsupported level '{level}'. Expected one of: {supported}.")
    return normalized


def _validate_project_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise ProjectBootstrapError("Project Name is required.")
    if normalized in RESERVED_PROJECT_NAMES:
        raise ProjectBootstrapError("Invalid Project Name.")
    if normalized in {".", ".."}:
        raise ProjectBootstrapError("Project Name cannot be '.' or '..'.")
    if normalized.endswith((" ", ".")):
        raise ProjectBootstrapError("Project Name cannot end with a space or period.")
    if INVALID_NAME_CHARS_RE.search(normalized):
        raise ProjectBootstrapError("Project Name contains invalid filesystem characters.")
    return normalized
