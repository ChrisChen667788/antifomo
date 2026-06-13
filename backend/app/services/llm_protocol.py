from __future__ import annotations

from typing import Protocol


class LLMService(Protocol):
    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        """Return JSON text for the given prompt template and variables."""
