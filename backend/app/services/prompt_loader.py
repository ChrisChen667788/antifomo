from pathlib import Path
import re


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt(name: str) -> str:
    prompt_path = PROMPT_DIR / name
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def render_prompt(prompt_name: str, variables: dict[str, str]) -> str:
    template = load_prompt(prompt_name)
    rendered = template
    for key, value in variables.items():
        rendered = re.sub(
            rf"\{{\{{\s*{re.escape(key)}\s*\}}\}}",
            lambda _match, replacement=str(value): replacement,
            rendered,
        )
    # Remove placeholders not explicitly provided.
    rendered = re.sub(r"\{\{\s*[a-zA-Z0-9_]+\s*\}\}", "", rendered)
    return rendered
