"""Every ready lesson script runs end to end against the stub endpoint, exactly as a learner runs it."""

import json

import pytest

from labkit.catalog import extra_installed, load_catalog
from labkit.config import repo_root


def _param(module, script):
    missing = [extra for extra in module.extras if extra != "all" and not extra_installed(extra)]
    marks = [pytest.mark.skip(reason=f"optional packages not installed: {', '.join(missing)}")] if missing else []
    return pytest.param(script, id=script.relative_to(repo_root()).as_posix(), marks=marks)


SCRIPTS = [_param(module, script) for module in load_catalog() for item in module.lessons if item.runnable for script in item.scripts()]
FIRST = "modules/01-foundations/01-first-llm-call/01_hello_llm.py"
STREAMING = "modules/01-foundations/01-first-llm-call/02_helpdesk_first_reply.py"


@pytest.mark.parametrize("script", SCRIPTS)
def test_script_runs_and_reports(script, run, tmp_path):
    result = run([str(script)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Step 1:" in result.stdout
    assert "Run summary:" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr
    logs = list((tmp_path / "logs").glob("*.jsonl"))
    assert len(logs) == 1
    events = [json.loads(line)["event"] for line in logs[0].read_text(encoding="utf-8").splitlines()]
    assert events[0] == "start" and events[-1] == "summary"


def test_tokens_are_counted(run):
    result = run([FIRST])
    assert "tokens: 21 in + 17 out = 38" in result.stdout
    assert "1 model call(s), 21 in + 17 out = 38 tokens" in result.stdout


def test_streaming_prints_the_reply_and_counts_tokens(run):
    result = run([STREAMING])
    assert "trained on text to predict what comes next" in result.stdout
    assert "21 in + 17 out = 38 tokens" in result.stdout


def test_endpoint_without_usage_is_handled(run):
    result = run([STREAMING], model="no-usage")
    assert result.returncode == 0
    assert "tokens not reported by this endpoint" in result.stdout


def test_raw_shows_the_wire_but_never_the_key(run):
    result = run([FIRST, "--raw"], key="super-secret-key-123")
    assert ">>> HTTP request: POST" in result.stdout
    assert "<<< HTTP response: 200" in result.stdout
    assert '"messages"' in result.stdout
    assert "super-secret-key-123" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    ("settings", "code", "expected"),
    [
        ({"configured": False}, 2, "not configured yet"),
        ({"key": "bad-key"}, 1, "rejected the API key (401)"),
        ({"model": "missing-model"}, 1, "not found' (404)"),
        ({"model": "rate-limited"}, 1, "(429)"),
        ({"base_url": "http://127.0.0.1:9/v1"}, 1, "Could not connect"),
    ],
    ids=["not-configured", "bad-key", "wrong-model", "rate-limited", "unreachable"],
)
def test_failures_are_explained_not_dumped(run, settings, code, expected):
    result = run([FIRST], **settings)
    assert result.returncode == code, result.stdout + result.stderr
    assert expected in result.stdout
    assert "Traceback" not in result.stdout + result.stderr
