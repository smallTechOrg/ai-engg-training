# Capability: doctor

`run doctor [--report] [--offline]` prints one line per check: PASS / WARN / FAIL / SKIP,
with a plain-language fix on anything not PASS. Exit code 0 if no FAIL.

Checks, in order:
1. Python version and platform.
2. Core packages import.
3. `.env` exists at the repo root; `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` set
   (placeholders from `.env.example` count as unset). Keys are shown masked.
4. Endpoint reachable: one minimal real chat call. Failures are classified: 401 bad key,
   404 model not found / wrong base URL, 429 rate limit, connection, timeout.
5. Model capabilities, each a tiny probe: `stream`, `tools`, `json`, `embeddings`.
   A missing capability is WARN and lists which lessons it affects.
6. Optional extras installed (per module group) — SKIP when absent, with the install command.
7. Services (added with the infra phases): each `<NAME>_URL` probed; SKIP when unset.

Results are cached in `.labkit/doctor.json` for `run list`. `--report` writes
`doctor-report.txt` (no secrets) for a learner to send to the instructor.
`--offline` skips checks 4-5.
