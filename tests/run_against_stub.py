"""Run one lesson script against the stub endpoint, without touching your .env or logs.

    uv run python tests/run_against_stub.py modules/01-foundations/01-first-llm-call/01_hello_llm.py
    uv run python tests/run_against_stub.py <script> --model no-usage -- --raw

Use it while writing a lesson: a script must finish cleanly here before it is marked ready.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import stub_server  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("script")
    parser.add_argument("--model", default="stub-model", help="stub-model, no-usage, no-tools, slow, missing-model, rate-limited")
    parser.add_argument("rest", nargs="*", help="arguments for the script, after --")
    args = parser.parse_args()
    server = stub_server.start()
    state = tempfile.mkdtemp(prefix="labkit-stub-")
    env = dict(
        os.environ,
        LABKIT_ENV_FILE=os.path.join(state, "no-such.env"),
        LABKIT_STATE_DIR=state,
        LLM_BASE_URL=f"http://127.0.0.1:{server.server_address[1]}/v1",
        LLM_API_KEY="test-key",
        LLM_MODEL=args.model,
        LLM_TIMEOUT="10",
    )
    code = subprocess.run([sys.executable, args.script, *args.rest], env=env, input="", text=True).returncode
    print(f"\n[stub run] exit code {code}")
    raise SystemExit(code)
