from __future__ import annotations
import time
from openai import OpenAI
from .config_loader import get_api_key
from .json_utils import loads_json_maybe

class LLMClient:
    def __init__(self, config: dict):
        self.config = config
        self.client = OpenAI(api_key=get_api_key(config), base_url=config["api"].get("base_url", "https://api.deepseek.com"))

    def chat_json(self, prompt: str) -> dict:
        model_cfg = self.config.get("model", {})
        api_cfg = self.config.get("api", {})
        max_retries = int(api_cfg.get("max_retries", 5))
        backoff = float(api_cfg.get("retry_backoff_seconds", 3))
        kwargs = {
            "model": model_cfg.get("name", "deepseek-chat"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": model_cfg.get("temperature", 0.2),
            "top_p": model_cfg.get("top_p", 0.9),
            "timeout": api_cfg.get("timeout_seconds", 120),
        }
        if model_cfg.get("json_mode", True):
            kwargs["response_format"] = {"type": "json_object"}
        last_err = None
        for i in range(max_retries):
            try:
                resp = self.client.chat.completions.create(**kwargs)
                text = resp.choices[0].message.content or ""
                obj = loads_json_maybe(text)
                if not isinstance(obj, dict):
                    raise ValueError("Model did not return a JSON object")
                return obj
            except Exception as e:
                last_err = e
                if i < max_retries - 1:
                    time.sleep(backoff * (i + 1))
        raise RuntimeError(f"LLM request failed after {max_retries} retries: {last_err}")
