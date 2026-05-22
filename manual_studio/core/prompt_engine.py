from __future__ import annotations

from typing import Any

from .jsonio import pretty
from .workspace import Workspace


class PromptEngine:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def load_prompt(self, name: str) -> str:
        return self.workspace.prompts_root.joinpath(name).read_text(encoding="utf-8")

    def render(self, name: str, input_obj: Any) -> str:
        base = self.load_prompt(name)
        policy_path = self.workspace.prompts_root.joinpath("00_json_output_policy.txt")
        json_policy = policy_path.read_text(encoding="utf-8") if policy_path.exists() else ""
        genre = self.workspace.load_config().get("genre", "")
        return (
            base.replace("{{JSON_OUTPUT_POLICY}}", json_policy)
            .replace("{{INPUT_JSON}}", pretty(input_obj))
            .replace("{{genre}}", genre)
        )
