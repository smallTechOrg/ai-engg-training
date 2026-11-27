# Roadmap

Each phase is user-testable. Gate commands run from the repo root.

## Phase 1 — Tooling, skeleton, first lesson

- **Goal:** fresh clone -> `setup` -> `run doctor` -> `run 01.1` prints a real reply;
  the whole journey is visible in `CURRICULUM.md`.
- **Slices:** (a) `labkit` config/client/lesson/errors; (b) catalog + CLI + map;
  (c) doctor; (d) bootstrap scripts + wrappers; (e) module skeleton + lesson 01.1;
  (f) stub endpoint + tests + CI matrix.
- **Key files:** `src/labkit/*`, `curriculum.toml`, `setup.sh`, `setup.ps1`, `run`,
  `run.cmd`, `modules/**`, `tests/**`, `.github/workflows/ci.yml`.
- **Gate:** `uv run pytest -q && uv run labkit doctor && uv run labkit run 01.1`
- **User test:** run setup, doctor, list, the menu, lesson 01.1 with and without `--raw`.

## Phase 2 — Foundations complete

- **Goal:** modules 00 and 01 fully written: messages and roles, streaming, parameters,
  tokens and context, prompt engineering, structured output, async calls; module capstone.
- **Slices:** one per lesson (disjoint folders).
- **Gate:** `uv run pytest -q && uv run labkit run 01 --all`
- **User test:** teach-through of module 01 from the READMEs alone.

## Phase 3 — One thin working script per code module (02-15)

- **Goal:** every code-centric module has one minimal `ready` lesson; extras wired;
  doctor reports extras and per-lesson capability needs.
- **Slices:** one per module (disjoint folders), plus extras in `pyproject.toml`.
- **Gate:** `uv sync --all-extras && uv run pytest -q && uv run labkit check --modules 02-15`
- **User test:** `run list` shows them ready; run one from each module.

## Phase 4 — Infra modules (16-19) and service checks

- **Goal:** thin lessons for deployment, monitoring, guardrails, n8n; compose files;
  service addresses in `.env`; doctor probes each service; lessons skip cleanly.
- **Gate:** `uv run pytest -q && uv run labkit doctor` (services SKIP or PASS, never crash)
- **User test:** with a service down the lesson explains what to start; with it up, it runs.

## Phase 5 — Live check and upkeep (live check done: `run check`)

- **Goal:** `run check` runs every ready lesson against the real endpoint and reports
  pass/fail per lesson; dependency-upgrade procedure documented.
- **Gate:** `uv run labkit check`

## Phase 6+ — Depth

Per module: full lesson set, scenario application in every lesson, module capstones,
module 20 capstone. One module per phase, order chosen by the instructor.
