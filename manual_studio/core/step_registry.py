from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    id: str
    label: str
    scope: str
    prompt: str | None
    description: str = ""
    is_local_action: bool = False
    writes_artifact: bool = False


STEPS = (
    Step("extract_chapter_glossary", "Extract Chapter Glossary", "chapter", "01_extract_volume_glossary.txt"),
    Step("merge_volume_glossary", "Merge Volume Glossary", "volume", "02_merge_volume_glossary.txt"),
    Step(
        "review_volume_glossary",
        "Review/Finalize Volume Glossary",
        "volume",
        None,
        "Use editor tab, then Approve Glossary",
        True,
        False,
    ),
    Step(
        "initialize_series_glossary_from_volume",
        "Initialize Series Glossary from Volume",
        "volume",
        None,
        "Copy the finalized volume glossary into the series glossary.",
        True,
        True,
    ),
    Step(
        "extract_chapter_relationships",
        "Extract Chapter Relationships",
        "chapter",
        "04_extract_volume_relationships.txt",
    ),
    Step("merge_volume_relationships", "Merge Volume Relationships", "volume", "05_merge_volume_relationships.txt"),
    Step(
        "review_volume_relationships",
        "Review/Finalize Volume Relationships",
        "volume",
        None,
        "Use editor tab, then Approve Relationships",
        True,
        False,
    ),
    Step(
        "initialize_series_relationships_from_volume",
        "Initialize Series Relationships from Volume",
        "volume",
        None,
        "Copy the finalized volume relationships into the series relationships canon.",
        True,
        True,
    ),
    Step(
        "build_active_volume_glossary",
        "Build Active Volume Glossary",
        "volume",
        None,
        "Scan the current volume source against Series Glossary and write the active volume glossary.",
        True,
        True,
    ),
    Step(
        "build_active_volume_relationships",
        "Build Active Volume Relationships",
        "volume",
        None,
        "Build active volume relationships from Series Relationships and active character tokens.",
        True,
        True,
    ),
    Step(
        "sync_volume_glossary_to_series",
        "Sync Finalized Glossary to Series",
        "volume",
        None,
        "Append new finalized volume glossary entries to Series Glossary and log conflicts.",
        True,
        True,
    ),
    Step(
        "sync_volume_relationships_to_series",
        "Sync Finalized Relationships to Series",
        "volume",
        None,
        "Append new finalized volume relationship rules to Series Relationships and log conflicts.",
        True,
        True,
    ),
    Step("build_segment_glossary", "Build Segment Glossary (AI)", "segment", "03_build_segment_glossary.txt"),
    Step(
        "build_segment_glossary_local",
        "Build Segment Glossary (Local)",
        "segment",
        None,
        "Run local text matching to build segment glossary",
        True,
        True,
    ),
    Step(
        "review_segment_glossary",
        "Review Segment Glossary",
        "segment",
        None,
        "Inspect/edit imported row in Segment Glossaries tab",
        True,
        False,
    ),
    Step("build_segment_pronouns", "Build Segment Pronouns (AI)", "segment", "06_build_segment_pronouns.txt"),
    Step(
        "build_segment_pronouns_local",
        "Build Segment Pronouns (Local)",
        "segment",
        None,
        "Run local text matching to build segment pronouns",
        True,
        True,
    ),
    Step(
        "review_segment_pronouns",
        "Review Segment Pronouns",
        "segment",
        None,
        "Inspect/edit imported row in Segment Pronouns tab",
        True,
        False,
    ),
    Step("build_segment_context", "Build Segment Context", "segment", "07_build_segment_context.txt"),
    Step("label_dialogue", "Label Dialogue", "segment", "08_label_dialogue.txt"),
    Step("translate", "Translate", "segment", "09_translate_labeled_segment.txt"),
    Step("qa", "QA (optional)", "segment", "10_qa_segment.txt"),
    Step("fix", "Fix (optional)", "segment", "11_fix_segment.txt"),
    Step("assemble", "Assemble Volume (local)", "volume", None, "Local assemble into release files", True, False),
)

STEPS_BY_ID = {step.id: step for step in STEPS}
STEP_IDS = tuple(step.id for step in STEPS)


def steps_for_scope(scope: str) -> tuple[Step, ...]:
    return tuple(step for step in STEPS if step.scope == scope)
