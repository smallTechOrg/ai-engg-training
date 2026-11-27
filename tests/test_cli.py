"""The launcher and the doctor, run as commands."""

import json

LABKIT = ["-m", "labkit.cli"]


def test_list_shows_every_module(run):
    result = run([*LABKIT, "list"])
    assert result.returncode == 0, result.stderr
    assert "Foundations: talking to an LLM" in result.stdout
    assert "Capstone" in result.stdout
    assert "? run doctor" in result.stdout  # doctor has not run in this isolated state dir


def test_menu_without_a_terminal_falls_back_to_the_list(run):
    result = run(LABKIT)
    assert result.returncode == 0
    assert "lesson(s) ready" in result.stdout


def test_run_one_script_by_id(run):
    result = run([*LABKIT, "01.1/1"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Hello, LLM" in result.stdout
    assert "first reply" not in result.stdout


def test_run_whole_lesson(run):
    result = run([*LABKIT, "run", "1.1"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Hello, LLM" in result.stdout and "first reply" in result.stdout


def test_planned_lesson_is_explained(run):
    result = run([*LABKIT, "02.1"])
    assert result.returncode == 3
    assert "planned but not written yet" in result.stdout


def test_unknown_lesson_and_command(run):
    assert run([*LABKIT, "99.9"]).returncode == 1
    result = run([*LABKIT, "frobnicate"])
    assert result.returncode == 1 and "Unknown command" in result.stdout


def test_doctor_passes_against_a_working_endpoint(run, tmp_path):
    result = run([*LABKIT, "doctor", "--report"])
    assert result.returncode == 0, result.stdout + result.stderr
    for line in ("Endpoint: a real chat call", "Capability: streaming", "Capability: tool calling", "Capability: JSON output"):
        assert f"PASS  {line}" in result.stdout, result.stdout
    assert "test-key" not in result.stdout
    cache = json.loads((tmp_path / ".labkit" / "doctor.json").read_text(encoding="utf-8"))
    assert cache["capabilities"] == {"chat": True, "stream": True, "tools": True, "json": True, "embeddings": None}
    listing = run([*LABKIT, "list"])
    assert "? run doctor" not in listing.stdout


def test_doctor_warns_about_a_model_without_tools(run):
    result = run([*LABKIT, "doctor"], model="no-tools")
    assert result.returncode == 0
    assert "WARN  Capability: tool calling" in result.stdout
    assert "limitation(s)" in result.stdout


def test_doctor_explains_a_bad_key_and_missing_settings(run):
    bad = run([*LABKIT, "doctor"], key="bad-key")
    assert bad.returncode == 1 and "rejected the API key (401)" in bad.stdout
    missing = run([*LABKIT, "doctor"], configured=False)
    assert missing.returncode == 1 and "Not set: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL" in missing.stdout


def test_doctor_offline_skips_the_endpoint(run):
    result = run([*LABKIT, "doctor", "--offline"], base_url="http://127.0.0.1:9/v1")
    assert result.returncode == 0 and "skipped (--offline)" in result.stdout


def test_next_follows_course_order_across_modules(run, tmp_path):
    first = run([*LABKIT, "next"])
    assert first.returncode == 0, first.stdout + first.stderr
    assert "Starting with 00.1" in first.stdout
    assert "Next: ./run 00.2" in first.stdout  # no terminal: it names the next lesson instead of asking
    (tmp_path / ".labkit" / "progress.json").write_text('{"last_lesson": "00.5"}', encoding="utf-8")
    crossing = run([*LABKIT, "next"])
    assert "Continuing with 01.1" in crossing.stdout
    assert "Next: ./run 01.2" in crossing.stdout


def test_whole_lesson_records_progress_but_one_script_does_not(run, tmp_path):
    progress = tmp_path / ".labkit" / "progress.json"
    run([*LABKIT, "01.1/1"])
    assert not progress.exists()
    run([*LABKIT, "01.1"])
    assert '"01.1"' in progress.read_text(encoding="utf-8")
