"""Settings come from the `.env` file at the repo root (or from real environment variables)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# Values copied unchanged from .env.example count as "not set".
PLACEHOLDERS = {"", "your-key", "your-model-name", "https://your-provider.example/v1"}
# Local model servers ignore the key, but the SDK insists on one: this stands in for it.
LOCAL_KEY = "not-needed-for-local-models"


class ConfigError(Exception):
    """The lesson cannot run because a setting is missing."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__("Missing settings: " + ", ".join(missing))


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """The folder holding curriculum.toml, found from this file or the current directory."""
    candidates = [Path(__file__).resolve().parents[2], Path.cwd(), *Path.cwd().parents]
    for folder in candidates:
        if (folder / "curriculum.toml").is_file():
            return folder
    return Path.cwd()


def state_dir(name: str) -> Path:
    """Where run logs (`logs`) and the doctor cache (`.labkit`) live. LABKIT_STATE_DIR relocates both."""
    base = os.environ.get("LABKIT_STATE_DIR", "").strip()
    return (Path(base) if base else repo_root()) / name


def is_local(url: str) -> bool:
    """True for endpoints on this machine (Ollama, LM Studio...), which need no real key."""
    return (urlparse(url).hostname or "") in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal")


def use_utf8_output() -> None:
    """Make printing safe on consoles with a legacy code page (older Windows terminals)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _get(name: str) -> str:
    value = os.environ.get(name, "").strip().strip('"').strip("'")
    return "" if value in PLACEHOLDERS else value


def mask(secret: str) -> str:
    """Show enough of a key to recognise it, never enough to use it."""
    if not secret:
        return "(not set)"
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:3]}...{secret[-2:]} ({len(secret)} chars)"


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    model: str
    embedding_base_url: str
    embedding_api_key: str
    embedding_model: str
    timeout: float
    env_file: Path
    env_file_exists: bool

    def missing(self) -> list[str]:
        required = {"LLM_BASE_URL": self.base_url, "LLM_API_KEY": self.api_key, "LLM_MODEL": self.model}
        return [name for name, value in required.items() if not value]

    @property
    def key_is_stand_in(self) -> bool:
        return self.api_key == LOCAL_KEY

    def require(self) -> "Settings":
        if self.missing():
            raise ConfigError(self.missing())
        return self


def load_settings() -> Settings:
    """Read settings. Real environment variables win over the .env file."""
    override = os.environ.get("LABKIT_ENV_FILE", "").strip()  # used by the tests
    env_file = Path(override) if override else repo_root() / ".env"
    load_dotenv(env_file, override=False)
    base_url = _get("LLM_BASE_URL").rstrip("/")
    api_key = _get("LLM_API_KEY") or (LOCAL_KEY if base_url and is_local(base_url) else "")
    try:
        timeout = float(_get("LLM_TIMEOUT") or 60)
    except ValueError:
        timeout = 60.0
    return Settings(
        base_url=base_url,
        api_key=api_key,
        model=_get("LLM_MODEL"),
        embedding_base_url=(_get("EMBEDDING_BASE_URL") or _get("LLM_BASE_URL")).rstrip("/"),
        embedding_api_key=_get("EMBEDDING_API_KEY") or api_key,
        embedding_model=_get("EMBEDDING_MODEL"),
        timeout=timeout,
        env_file=env_file,
        env_file_exists=env_file.is_file(),
    )
