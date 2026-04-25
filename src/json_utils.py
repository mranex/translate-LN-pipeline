from __future__ import annotations
import json, re
from typing import Any

def loads_json_maybe(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end+1])
        raise

def dumps_json(obj: Any, indent: int = 2) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=indent)

def item_id_from_record(rec: dict) -> str:
    if rec.get("segment"):
        return str(rec["segment"])
    return f"c{int(rec.get('chapter', 0)):03d}"
