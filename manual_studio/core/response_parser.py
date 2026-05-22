from __future__ import annotations

import json
import re
from typing import Any


def strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = strip_fences(text)
    try:
        obj = json.loads(cleaned)
        if not isinstance(obj, dict):
            raise ValueError("Top-level JSON must be an object.")
        return obj
    except Exception:
        start = cleaned.find("{")
        if start >= 0:
            candidate = _extract_outermost_object(cleaned, start)
            if candidate is not None:
                obj = json.loads(candidate)
                if not isinstance(obj, dict):
                    raise ValueError("Top-level JSON must be an object.")
                return obj
        raise


def _extract_outermost_object(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None
