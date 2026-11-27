# Capability: launcher

Entry points: `./run` (POSIX), `run.cmd` (Windows), or `uv run labkit`.

| Command | Behaviour |
|---|---|
| `run` (no args) | Numbered menu: pick a module, then a lesson, then a script. `q` quits. Non-interactive stdin prints the list instead. |
| `run list` | Every module and lesson with status (`ready`/`draft`/`planned`) and, for ready lessons, whether their needs are met (from the doctor cache; `?` if doctor has not run). |
| `run 01.1` | Runs every script of the lesson in order, pausing between scripts when interactive. |
| `run 01.1/2` | Runs one script. Extra arguments (`--raw`) pass through. |
| `run doctor` | See doctor capability. |
| `run map` | Regenerates `CURRICULUM.md` from `curriculum.toml`. |

Planned lessons cannot be run: the launcher says so and points to the map.
Scripts are executed as subprocesses with the project interpreter and repo root as cwd.
