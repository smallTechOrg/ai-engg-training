# Capability: bootstrap

**Goal:** from a fresh clone on a machine with no usable Python, one command produces a
working environment.

- `setup.sh` (macOS, Linux, WSL, VMs) and `setup.cmd` -> `setup.ps1` (Windows PowerShell
  5.1+; the `.cmd` wrapper avoids execution-policy blocks).
- Steps: find `uv` (PATH, then `~/.local/bin`, `~/.cargo/bin`); if absent install it with
  the official installer into the user's home (no admin rights); `uv sync` (downloads
  Python 3.12 if needed); copy `.env.example` to `.env` if missing; print next steps.
- Idempotent: re-running is safe and fast. Never overwrites an existing `.env`.
- `--all` / `-All` installs every optional extra; default installs the base only.
- Failure output names the step that failed and the likely cause (proxy, no network).
- Fallback documented in README for machines where uv cannot be installed:
  `python -m venv .venv` + `pip install -e .`.
