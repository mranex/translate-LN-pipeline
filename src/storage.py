from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .json_utils import dumps_json

def read_json(path: str | Path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))

def write_json(path: str | Path, obj: Any):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dumps_json(obj) + "\n", encoding="utf-8")

def append_jsonl(path: str | Path, obj: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def read_jsonl(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out

def success_ids(path: str | Path) -> set[str]:
    return {str(r.get("item_id")) for r in read_jsonl(path) if r.get("status") == "success"}

def load_volume_source(config: dict, volume: int) -> list[dict]:
    path = Path(config["paths"]["source_dir"]) / f"volume_{volume:02d}.json"
    data = read_json(path)
    if data is None:
        raise FileNotFoundError(path)
    if isinstance(data, dict) and "chapters" in data:
        return data["chapters"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported source schema: {path}")

def load_volume_segments(config: dict, volume: int) -> list[dict]:
    path = Path(config["paths"]["segments_dir"]) / f"volume_{volume:02d}.segments.json"
    data = read_json(path)
    if data is None:
        raise FileNotFoundError(path)
    if isinstance(data, dict) and "segments" in data:
        return data["segments"]
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported segment schema: {path}")
