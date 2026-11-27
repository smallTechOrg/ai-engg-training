"""Shared fixtures: a local stub endpoint and a helper that runs commands the way a learner does."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))

import stub_server  # noqa: E402


@pytest.fixture(scope="session")
def stub():
    server = stub_server.start()
    yield server
    server.shutdown()


@pytest.fixture
def run(stub, tmp_path):
    """run([...args], **settings) -> CompletedProcess, pointed at the stub and isolated from the real .env."""

    def _run(args: list[str], *, model: str = "stub-model", key: str = "test-key", base_url: str | None = None, configured: bool = True):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("LLM_", "EMBEDDING_"))}
        env.update(
            LABKIT_ENV_FILE=str(tmp_path / "no-such.env"),
            LABKIT_STATE_DIR=str(tmp_path),
            PYTHONIOENCODING="utf-8",
            NO_COLOR="1",
            COLUMNS="200",
        )
        if configured:
            env.update(
                LLM_BASE_URL=base_url or f"http://127.0.0.1:{stub.server_address[1]}/v1",
                LLM_API_KEY=key,
                LLM_MODEL=model,
                LLM_TIMEOUT="10",
            )
        return subprocess.run([sys.executable, *args], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)

    return _run
