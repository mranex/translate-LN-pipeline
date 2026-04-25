from __future__ import annotations
import json, os
from pathlib import Path
from dotenv import load_dotenv

def load_config(path: str | Path = "config/config.json") -> dict:
    load_dotenv()
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    data["_config_path"] = str(p)
    return data

def get_api_key(config: dict) -> str:
    env = config.get("api", {}).get("api_key_env", "DEEPSEEK_API_KEY")
    key = os.getenv(env)
    if not key:
        raise RuntimeError(f"Missing API key environment variable: {env}")
    return key
