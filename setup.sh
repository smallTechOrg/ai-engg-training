#!/usr/bin/env sh
# Set up this repo on macOS, Linux, WSL or a VM. Needs no Python: uv downloads one.
#   ./setup.sh          install the base (enough for the first modules)
#   ./setup.sh --all    also install every optional framework
# Safe to run again at any time.
set -eu
cd "$(dirname "$0")"

say()  { printf '\n==> %s\n' "$1"; }
fail() { printf '\nSETUP FAILED at: %s\n%s\n' "$1" "$2" >&2; exit 1; }

find_uv() {
    if command -v uv >/dev/null 2>&1; then command -v uv; return 0; fi
    for dir in "$HOME/.local/bin" "$HOME/.cargo/bin"; do
        if [ -x "$dir/uv" ]; then echo "$dir/uv"; return 0; fi
    done
    return 1
}

say "Step 1 of 3: uv (the tool that installs Python and the packages)"
if UV=$(find_uv); then
    echo "Found: $UV"
else
    echo "Not found. Installing into your home folder (no admin rights needed)..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh || fail "installing uv" "Check your internet connection or proxy. Manual install: https://docs.astral.sh/uv/getting-started/installation/"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh || fail "installing uv" "Check your internet connection or proxy. Manual install: https://docs.astral.sh/uv/getting-started/installation/"
    else
        fail "installing uv" "Neither curl nor wget is available. Install one of them, or install uv by hand: https://docs.astral.sh/uv/getting-started/installation/"
    fi
    UV=$(find_uv) || fail "locating uv after install" "Open a new terminal and run ./setup.sh again."
fi

say "Step 2 of 3: Python and packages"
if [ "${1:-}" = "--all" ]; then
    "$UV" sync --all-extras || fail "installing packages" "Check your internet connection or proxy, then run ./setup.sh --all again."
else
    "$UV" sync || fail "installing packages" "Check your internet connection or proxy, then run ./setup.sh again."
fi

say "Step 3 of 3: settings file"
if [ -f .env ]; then
    echo ".env already exists: left untouched."
else
    cp .env.example .env
    echo "Created .env from .env.example."
fi

cat <<'DONE'

Setup complete. Next:
  1. Open .env and set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL.
  2. ./run doctor      check everything works
  3. ./run 01.1        run the first lesson
  4. ./run             browse all lessons
DONE
