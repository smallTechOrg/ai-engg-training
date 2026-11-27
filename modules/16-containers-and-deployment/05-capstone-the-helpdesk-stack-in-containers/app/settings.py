"""Start-up settings: environment variables, with secrets readable from NAME_FILE (Docker secrets)."""

import os
from pathlib import Path

REQUIRED = ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY")


def get(name: str, default: str = "") -> str:
    path = os.environ.get(f"{name}_FILE", "").strip()
    if path:
        return Path(path).read_text(encoding="utf-8").strip()
    return os.environ.get(name, default).strip()


def problems() -> list[str]:
    """Everything wrong with the configuration, all at once (empty list = fine)."""
    found = []
    for name in REQUIRED:
        try:
            if not get(name):
                found.append(f"{name} is not set")
        except OSError:
            found.append(f"{name}_FILE cannot be read")
    if get("LLM_BASE_URL") and not get("LLM_BASE_URL").startswith(("http://", "https://")):
        found.append("LLM_BASE_URL must start with http:// or https://")
    return found
