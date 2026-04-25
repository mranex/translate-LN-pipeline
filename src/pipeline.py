from __future__ import annotations
import concurrent.futures as cf
from pathlib import Path
from threading import Lock
from typing import Callable
from .api_client import LLMClient
from .prompt_loader import render, with_json_policy
from .storage import append_jsonl, read_jsonl, success_ids, read_json, write_json, load_volume_source, load_volume_segments
from .json_utils import item_id_from_record

def run_batch(config: dict, items: list[dict], output_path: Path, worker: Callable[[dict], dict]):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overwrite = bool(config.get("runtime", {}).get("overwrite_existing", False))
    done = set() if overwrite else success_ids(output_path)
    max_workers = int(config.get("runtime", {}).get("max_workers", 4))
    lock = Lock()
    pending = []
    for item in items:
        iid = item_id_from_record(item)
        if iid not in done:
            pending.append((iid, item))
    def call(pair):
        iid, item = pair
        try:
            result = worker(item)
            return {"item_id": iid, "status": "success", "result": result}
        except Exception as e:
            return {"item_id": iid, "status": "failed", "error": str(e)}
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for fut in cf.as_completed([ex.submit(call, pair) for pair in pending]):
            row = fut.result()
            with lock:
                append_jsonl(output_path, row)
            print(f"[{output_path.name}] {row['item_id']}: {row['status']}")

def latest_success_map(jsonl_path: Path) -> dict[str, dict]:
    out = {}
    for row in read_jsonl(jsonl_path):
        if row.get("status") == "success":
            out[str(row.get("item_id"))] = row.get("result", {})
    return out

def load_final_glossary(config: dict, volume: int) -> dict:
    p = Path(config["paths"]["canon_dir"]) / "glossary" / "finalized" / f"volume_{volume:02d}.glossary.json"
    data = read_json(p)
    if data is None:
        raise FileNotFoundError(f"Missing finalized glossary: {p}")
    return data

def load_final_relationships(config: dict, volume: int) -> dict:
    p = Path(config["paths"]["canon_dir"]) / "relationships" / "finalized" / f"volume_{volume:02d}.relationships.json"
    data = read_json(p)
    if data is None:
        raise FileNotFoundError(f"Missing finalized relationships: {p}")
    return data

def extract_glossary(config: dict, volume: int):
    client = LLMClient(config); tmpl = with_json_policy(config, "01_extract_volume_glossary.txt")
    chapters = load_volume_source(config, volume)
    output = Path(config["paths"]["working_dir"]) / "glossary_extractions" / f"volume_{volume:02d}.glossary_extractions.jsonl"
    def worker(ch: dict):
        item = {"volume": volume, "chapter": ch.get("chapter"), "segment": ch.get("segment"), "name": ch.get("name"), "content": ch.get("content", "")}
        return client.chat_json(render(tmpl, INPUT_JSON=item))
    run_batch(config, chapters, output, worker)

def merge_glossary(config: dict, volume: int, previous_finalized: bool = True):
    client = LLMClient(config); tmpl = with_json_policy(config, "02_merge_volume_glossary.txt")
    extraction_path = Path(config["paths"]["working_dir"]) / "glossary_extractions" / f"volume_{volume:02d}.glossary_extractions.jsonl"
    extractions = [r.get("result") for r in read_jsonl(extraction_path) if r.get("status") == "success"]
    prev = None
    if previous_finalized and volume > 1:
        prev = read_json(Path(config["paths"]["canon_dir"]) / "glossary" / "finalized" / f"volume_{volume-1:02d}.glossary.json")
    result = client.chat_json(render(tmpl, INPUT_JSON={"volume": volume, "chapter_extractions": extractions, "previous_finalized_glossary": prev}))
    out = Path(config["paths"]["canon_dir"]) / "glossary" / "drafts" / f"volume_{volume:02d}.glossary.draft.json"
    write_json(out, result); print(f"Wrote {out}")

def approve_glossary(config: dict, volume: int, from_file: str | None = None, overwrite: bool = False):
    src = Path(from_file) if from_file else Path(config["paths"]["canon_dir"]) / "glossary" / "drafts" / f"volume_{volume:02d}.glossary.draft.json"
    dst = Path(config["paths"]["canon_dir"]) / "glossary" / "finalized" / f"volume_{volume:02d}.glossary.json"
    if dst.exists() and not overwrite: raise FileExistsError(f"{dst} exists. Use --overwrite.")
    write_json(dst, read_json(src)); print(f"Approved glossary: {dst}")

def build_segment_glossary(config: dict, volume: int):
    client = LLMClient(config); tmpl = with_json_policy(config, "03_build_segment_glossary.txt")
    segments = load_volume_segments(config, volume); glossary = load_final_glossary(config, volume)
    output = Path(config["paths"]["working_dir"]) / "segment_glossaries" / f"volume_{volume:02d}.segment_glossaries.jsonl"
    entries = glossary.get("volume_merge_glossary") or glossary.get("entries") or []
    def deterministic_hits(content: str):
        return [e for e in entries if str(e.get("source", "")) and str(e.get("source", "")) in content]
    def worker(seg: dict):
        return client.chat_json(render(tmpl, INPUT_JSON={"volume": volume, "chapter": seg.get("chapter"), "segment": seg.get("segment"), "name": seg.get("name"), "content": seg.get("content", ""), "volume_glossary": glossary, "deterministic_source_hits": deterministic_hits(seg.get("content", ""))}))
    run_batch(config, segments, output, worker)

def extract_relationships(config: dict, volume: int):
    client = LLMClient(config); tmpl = with_json_policy(config, "04_extract_volume_relationships.txt")
    segments = load_volume_segments(config, volume); glossary = load_final_glossary(config, volume)
    output = Path(config["paths"]["working_dir"]) / "relationship_extractions" / f"volume_{volume:02d}.relationships_extractions.jsonl"
    def worker(seg: dict):
        return client.chat_json(render(tmpl, INPUT_JSON={"volume": volume, "chapter": seg.get("chapter"), "segment": seg.get("segment"), "name": seg.get("name"), "content": seg.get("content", ""), "volume_glossary": glossary}))
    run_batch(config, segments, output, worker)

def merge_relationships(config: dict, volume: int, previous_finalized: bool = True):
    client = LLMClient(config); tmpl = with_json_policy(config, "05_merge_volume_relationships.txt")
    extraction_path = Path(config["paths"]["working_dir"]) / "relationship_extractions" / f"volume_{volume:02d}.relationships_extractions.jsonl"
    extractions = [r.get("result") for r in read_jsonl(extraction_path) if r.get("status") == "success"]
    prev = None
    if previous_finalized and volume > 1:
        prev = read_json(Path(config["paths"]["canon_dir"]) / "relationships" / "finalized" / f"volume_{volume-1:02d}.relationships.json")
    result = client.chat_json(render(tmpl, INPUT_JSON={"volume": volume, "relationship_extractions": extractions, "previous_finalized_relationships": prev}))
    out = Path(config["paths"]["canon_dir"]) / "relationships" / "drafts" / f"volume_{volume:02d}.relationships.draft.json"
    write_json(out, result); print(f"Wrote {out}")

def approve_relationships(config: dict, volume: int, from_file: str | None = None, overwrite: bool = False):
    src = Path(from_file) if from_file else Path(config["paths"]["canon_dir"]) / "relationships" / "drafts" / f"volume_{volume:02d}.relationships.draft.json"
    dst = Path(config["paths"]["canon_dir"]) / "relationships" / "finalized" / f"volume_{volume:02d}.relationships.json"
    if dst.exists() and not overwrite: raise FileExistsError(f"{dst} exists. Use --overwrite.")
    write_json(dst, read_json(src)); print(f"Approved relationships: {dst}")

def build_segment_pronouns(config: dict, volume: int):
    client = LLMClient(config); tmpl = with_json_policy(config, "06_build_segment_pronouns.txt")
    segments = load_volume_segments(config, volume); glossary_map = latest_success_map(Path(config["paths"]["working_dir"]) / "segment_glossaries" / f"volume_{volume:02d}.segment_glossaries.jsonl")
    relationships = load_final_relationships(config, volume)
    output = Path(config["paths"]["canon_dir"]) / "segment_pronouns" / f"volume_{volume:02d}.segment_pronouns.jsonl"
    def worker(seg: dict):
        iid = item_id_from_record(seg)
        return client.chat_json(render(tmpl, INPUT_JSON={"volume": volume, "chapter": seg.get("chapter"), "segment": seg.get("segment"), "name": seg.get("name"), "content": seg.get("content", ""), "segment_glossary": glossary_map.get(iid, {}), "volume_relationship_pronoun_canon": relationships}))
    run_batch(config, segments, output, worker)

def build_segment_context(config: dict, volume: int):
    client = LLMClient(config); tmpl = with_json_policy(config, "07_build_segment_context.txt")
    segments = load_volume_segments(config, volume)
    sg = latest_success_map(Path(config["paths"]["working_dir"]) / "segment_glossaries" / f"volume_{volume:02d}.segment_glossaries.jsonl")
    sp = latest_success_map(Path(config["paths"]["canon_dir"]) / "segment_pronouns" / f"volume_{volume:02d}.segment_pronouns.jsonl")
    output = Path(config["paths"]["working_dir"]) / "segment_contexts" / f"volume_{volume:02d}.segment_contexts.jsonl"
    def worker(seg: dict):
        iid = item_id_from_record(seg)
        return client.chat_json(render(tmpl, INPUT_JSON={"volume": volume, "chapter": seg.get("chapter"), "segment": seg.get("segment"), "name": seg.get("name"), "content": seg.get("content", ""), "segment_glossary": sg.get(iid, {}), "segment_pronoun_table": sp.get(iid, {})}))
    run_batch(config, segments, output, worker)

def label_dialogue(config: dict, volume: int):
    client = LLMClient(config); tmpl = with_json_policy(config, "08_label_dialogue.txt")
    segments = load_volume_segments(config, volume)
    sg = latest_success_map(Path(config["paths"]["working_dir"]) / "segment_glossaries" / f"volume_{volume:02d}.segment_glossaries.jsonl")
    sp = latest_success_map(Path(config["paths"]["canon_dir"]) / "segment_pronouns" / f"volume_{volume:02d}.segment_pronouns.jsonl")
    sc = latest_success_map(Path(config["paths"]["working_dir"]) / "segment_contexts" / f"volume_{volume:02d}.segment_contexts.jsonl")
    output = Path(config["paths"]["working_dir"]) / "dialogue_labels" / f"volume_{volume:02d}.dialogue_labels.jsonl"
    def worker(seg: dict):
        iid = item_id_from_record(seg)
        return client.chat_json(render(tmpl, INPUT_JSON={"volume": volume, "chapter": seg.get("chapter"), "segment": seg.get("segment"), "name": seg.get("name"), "content": seg.get("content", ""), "segment_glossary": sg.get(iid, {}), "segment_pronoun_table": sp.get(iid, {}), "segment_context": sc.get(iid, {}), "dialogue_labeling_config": config.get("dialogue_labeling", {})}))
    run_batch(config, segments, output, worker)

def translate(config: dict, volume: int):
    client = LLMClient(config); tmpl = with_json_policy(config, "09_translate_labeled_segment.txt")
    segments = load_volume_segments(config, volume)
    sg = latest_success_map(Path(config["paths"]["working_dir"]) / "segment_glossaries" / f"volume_{volume:02d}.segment_glossaries.jsonl")
    sp = latest_success_map(Path(config["paths"]["canon_dir"]) / "segment_pronouns" / f"volume_{volume:02d}.segment_pronouns.jsonl")
    sc = latest_success_map(Path(config["paths"]["working_dir"]) / "segment_contexts" / f"volume_{volume:02d}.segment_contexts.jsonl")
    dl = latest_success_map(Path(config["paths"]["working_dir"]) / "dialogue_labels" / f"volume_{volume:02d}.dialogue_labels.jsonl")
    output = Path(config["paths"]["working_dir"]) / "translations" / "draft" / f"volume_{volume:02d}.translated.jsonl"
    def worker(seg: dict):
        iid = item_id_from_record(seg)
        return client.chat_json(render(tmpl, INPUT_JSON={"volume": volume, "chapter": seg.get("chapter"), "segment": seg.get("segment"), "name": seg.get("name"), "segment_glossary": sg.get(iid, {}), "segment_pronoun_table": sp.get(iid, {}), "segment_context": sc.get(iid, {}), "dialogue_labels": dl.get(iid, {})}))
    run_batch(config, segments, output, worker)

def assemble(config: dict, volume: int, fixed: bool = False):
    segments = load_volume_segments(config, volume)
    path = Path(config["paths"]["working_dir"]) / "translations" / ("fixed" if fixed else "draft") / (f"volume_{volume:02d}.fixed.jsonl" if fixed else f"volume_{volume:02d}.translated.jsonl")
    field = "fixed_translation" if fixed else "translation"
    tr = latest_success_map(path)
    chapters = {}
    for seg in segments:
        iid = item_id_from_record(seg); res = tr.get(iid, {}); text = res.get(field) or res.get("translation") or ""
        ch = int(seg.get("chapter", 0)); chapters.setdefault(ch, {"chapter": ch, "name": seg.get("name", ""), "segments": []})
        chapters[ch]["segments"].append({"segment": seg.get("segment"), "translation": text})
    out_chapters = []
    for ch in sorted(chapters):
        c = chapters[ch]; c["content"] = "\n\n".join(s["translation"] for s in c["segments"] if s.get("translation")); out_chapters.append(c)
    release = {"volume": volume, "chapters": out_chapters}; base = Path(config["paths"]["release_dir"])
    write_json(base / f"volume_{volume:02d}.vi.json", release)
    md = [f"# Volume {volume:02d}"]
    for c in out_chapters:
        md.append(f"\n## Chapter {c['chapter']} — {c.get('name','')}\n"); md.append(c.get("content", ""))
    (base / f"volume_{volume:02d}.vi.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")
    print(f"Wrote release volume_{volume:02d}.vi.json/.md")

def qa(config: dict, volume: int):
    client = LLMClient(config); tmpl = with_json_policy(config, "10_qa_segment.txt")
    segments = load_volume_segments(config, volume)
    sg = latest_success_map(Path(config["paths"]["working_dir"]) / "segment_glossaries" / f"volume_{volume:02d}.segment_glossaries.jsonl")
    sp = latest_success_map(Path(config["paths"]["canon_dir"]) / "segment_pronouns" / f"volume_{volume:02d}.segment_pronouns.jsonl")
    sc = latest_success_map(Path(config["paths"]["working_dir"]) / "segment_contexts" / f"volume_{volume:02d}.segment_contexts.jsonl")
    dl = latest_success_map(Path(config["paths"]["working_dir"]) / "dialogue_labels" / f"volume_{volume:02d}.dialogue_labels.jsonl")
    tr = latest_success_map(Path(config["paths"]["working_dir"]) / "translations" / "draft" / f"volume_{volume:02d}.translated.jsonl")
    output = Path(config["paths"]["working_dir"]) / "translations" / "qa" / f"volume_{volume:02d}.qa.jsonl"
    def worker(seg: dict):
        iid = item_id_from_record(seg)
        return client.chat_json(render(tmpl, INPUT_JSON={"volume": volume, "chapter": seg.get("chapter"), "segment": seg.get("segment"), "name": seg.get("name"), "source_content": seg.get("content", ""), "segment_glossary": sg.get(iid, {}), "segment_pronoun_table": sp.get(iid, {}), "segment_context": sc.get(iid, {}), "dialogue_labels": dl.get(iid, {}), "translation": tr.get(iid, {})}))
    run_batch(config, segments, output, worker)

def fix(config: dict, volume: int):
    client = LLMClient(config); tmpl = with_json_policy(config, "11_fix_segment.txt")
    segments = load_volume_segments(config, volume)
    sg = latest_success_map(Path(config["paths"]["working_dir"]) / "segment_glossaries" / f"volume_{volume:02d}.segment_glossaries.jsonl")
    sp = latest_success_map(Path(config["paths"]["canon_dir"]) / "segment_pronouns" / f"volume_{volume:02d}.segment_pronouns.jsonl")
    sc = latest_success_map(Path(config["paths"]["working_dir"]) / "segment_contexts" / f"volume_{volume:02d}.segment_contexts.jsonl")
    dl = latest_success_map(Path(config["paths"]["working_dir"]) / "dialogue_labels" / f"volume_{volume:02d}.dialogue_labels.jsonl")
    tr = latest_success_map(Path(config["paths"]["working_dir"]) / "translations" / "draft" / f"volume_{volume:02d}.translated.jsonl")
    qa_map = latest_success_map(Path(config["paths"]["working_dir"]) / "translations" / "qa" / f"volume_{volume:02d}.qa.jsonl")
    output = Path(config["paths"]["working_dir"]) / "translations" / "fixed" / f"volume_{volume:02d}.fixed.jsonl"
    def worker(seg: dict):
        iid = item_id_from_record(seg)
        return client.chat_json(render(tmpl, INPUT_JSON={"volume": volume, "chapter": seg.get("chapter"), "segment": seg.get("segment"), "name": seg.get("name"), "source_content": seg.get("content", ""), "segment_glossary": sg.get(iid, {}), "segment_pronoun_table": sp.get(iid, {}), "segment_context": sc.get(iid, {}), "dialogue_labels": dl.get(iid, {}), "translation": tr.get(iid, {}), "qa_report": qa_map.get(iid, {})}))
    run_batch(config, segments, output, worker)

def glossary_prep(config: dict, volumes: list[int]):
    for v in volumes:
        extract_glossary(config, v); merge_glossary(config, v)

def relationship_prep(config: dict, volume: int):
    extract_relationships(config, volume); merge_relationships(config, volume)

def run_translation(config: dict, volume: int):
    build_segment_glossary(config, volume); build_segment_pronouns(config, volume); build_segment_context(config, volume); label_dialogue(config, volume); translate(config, volume); assemble(config, volume, fixed=False)
