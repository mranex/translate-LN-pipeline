from __future__ import annotations

import copy
import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any


def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty(obj) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[Any]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def backup(path: Path) -> None:
    if path.exists():
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, path.with_suffix(path.suffix + "." + stamp + ".bak"))


def result(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("result")
    return value if isinstance(value, dict) else row


def iid(row: dict[str, Any]) -> str:
    resolved = result(row)
    return str(row.get("item_id") or resolved.get("item_id") or resolved.get("segment") or "")


def item_id_from_record(record: dict[str, Any]) -> str:
    return str(record.get("segment") or f"c{int(record.get('chapter', 0)):03d}")
