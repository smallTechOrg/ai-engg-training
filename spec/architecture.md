# Architecture

## Stack

| Choice | Rationale |
|---|---|
| Python 3.12 (pinned in `.python-version`) | Supported by every framework in scope; 3.13+ still lags for some. |
| uv (environment, lockfile, Python download) | One static binary installs Python itself, so a machine with no or broken Python still works. Assumed: no stated preference. |
| `openai` SDK | The reference client for OpenAI-compatible endpoints; lessons call it directly so the code learners read is the real API. |
| `python-dotenv` | `.env` loading, loaded from the repo root by absolute path (`LABKIT_ENV_FILE` overrides it for tests). |
| `rich` | Readable projector output; handles Windows consoles. |
| pytest + a stdlib stub endpoint | Lessons are executed as real subprocesses against a local fake of the API; no secrets, no mocks inside lesson code. |
| GitHub Actions | Matrix on ubuntu, macos, windows. |

Heavy frameworks (LangChain, LangGraph, CrewAI, MCP SDK, vector stores, FastAPI...) are
**optional extras** in `pyproject.toml`, one per module group, all resolved in the single
`uv.lock`. Base install stays small and fast.

No database. No web UI for the tooling. State on disk: `logs/` (run logs, ignored) and
`.labkit/` (doctor cache, ignored); `LABKIT_STATE_DIR` relocates both.

The HTTP client is obtained from the SDK (`openai.DefaultHttpxClient`), never imported
directly: openai 3.x ships its own HTTP library.

## Layout

```
setup.sh / setup.cmd+ps1    bootstrap: install uv if absent, uv sync, create .env
run / run.cmd               launcher wrappers -> `uv run labkit ...`
curriculum.toml             single source of truth: modules, lessons, status, needs
CURRICULUM.md               generated from curriculum.toml (`run map`); test keeps it in sync
.env.example                every setting documented
pyproject.toml, uv.lock, .python-version
src/labkit/
  config.py                 Settings from <repo>/.env; repo-root discovery
  client.py                 get_client() -> openai.OpenAI with wire logging hooks
  lesson.py                 @lesson decorator + Lesson context (steps, show, stream, usage, log)
  errors.py                 friendly error translation
  catalog.py                parse curriculum.toml; resolve lesson ids
  doctor.py                 checks + report
  cli.py                    list | run | doctor | map | menu
modules/
  NN-name/README.md         module overview
  NN-name/MM-lesson/README.md, 01_*.py, 02_*.py
tests/
  stub_server.py            OpenAI-compatible fake (chat, streaming, tools, embeddings)
  test_*.py
spec/                       this design
```

## Conventions

- **Lesson ids** are `MM.L` (module.lesson), e.g. `01.1`; a script is `01.1/2`.
- **Lessons import only `labkit` and third-party packages**, never another lesson.
- **Lesson code calls the provider SDK directly.** `labkit` never hides the API call
  being taught; it supplies the client, printing, usage totals, logs and error handling.
- **Every script is `python path/to/script.py`-runnable** and accepts `--raw`, parsed by
  the `@lesson` decorator.
- **Settings** are `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, optional
  `EMBEDDING_BASE_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`; services are `<NAME>_URL`.
  `LLM_*` names are used (not `OPENAI_*`) so a stray global key cannot be picked up silently.
  `LLM_API_KEY` may be empty when `LLM_BASE_URL` is on this machine (local model servers).
- **Status values** in `curriculum.toml`: `ready`, `draft`, `planned`.
- **Needs**: a lesson lists model capabilities (`chat`, `stream`, `tools`, `json`,
  `embeddings`), extras and services; the launcher and doctor report against them.
- **No client names, no real personal data** anywhere; scenario data is invented.
- **Exit codes**: 0 ok, 1 lesson failed with a friendly message, 2 not configured, 3 skipped (missing service/extra).
- Secrets: `.env` is ignored, never printed; doctor masks keys.
