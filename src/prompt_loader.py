from __future__ import annotations
from pathlib import Path
import json

def load_prompt(config: dict, name: str) -> str:
    return (Path(config["paths"]["prompts_dir"]) / name).read_text(encoding="utf-8")

def render(template: str, **kwargs) -> str:
    out = template
    for k, v in kwargs.items():
        if not isinstance(v, str):
            v = json.dumps(v, ensure_ascii=False, indent=2)
        out = out.replace("{{" + k + "}}", v)
    return out

def with_json_policy(config: dict, prompt_name: str) -> str:
    base = load_prompt(config, prompt_name)
    policy = load_prompt(config, "00_json_output_policy.txt")
    return base.replace("{{JSON_OUTPUT_POLICY}}", policy)
