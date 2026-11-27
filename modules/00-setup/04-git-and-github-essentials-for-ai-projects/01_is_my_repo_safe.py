"""00.4/1  Is my repo safe to push?

Before any `git push`, ask two questions about an AI project. Are the files that hold
secrets and local clutter IGNORED? Is any of them already TRACKED? This script asks git
both questions about this repo. It only reads and changes nothing. It makes no model calls.

Run it:   ./run 00.4/1          (Windows: run 00.4/1)
     or:  python modules/00-setup/04-git-and-github-essentials-for-ai-projects/01_is_my_repo_safe.py
"""

import shutil
import subprocess

from labkit import lesson, repo_root

# Paths an AI project must keep out of version control, and why.
MUST_BE_IGNORED = [
    (".env", "holds your API key"),
    (".venv/", "installed packages: large, and rebuilt from the lockfile"),
    ("logs/", "run logs: may contain prompts, replies and personal data"),
    (".labkit/", "local cache from the doctor"),
    ("__pycache__/", "compiled Python files"),
]

# Files that SHOULD be committed, to show the other side.
MUST_BE_TRACKED = [".env.example", ".gitignore", "pyproject.toml", "uv.lock"]


def git(*args: str) -> subprocess.CompletedProcess:
    """Run a read-only git command in the repo and capture what it prints."""
    return subprocess.run(["git", *args], cwd=repo_root(), capture_output=True, text=True, encoding="utf-8", errors="replace")


@lesson("00.4/1", "Is my repo safe to push?")
def main(ctx):
    ctx.step("Is git here, and is this a repository?")
    if shutil.which("git") is None:
        ctx.note("git is not installed (or not on PATH), so there is nothing to check on this machine.")
        ctx.note("Install it from https://git-scm.com/downloads and run this script again.")
        return
    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        ctx.note("This folder is not a git repository (it may have been downloaded as a zip).")
        ctx.note("The checks below need one. `git init` creates it; `git clone` gives you one with history.")
        return
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    ctx.note(f"{git('--version').stdout.strip()}, on branch '{branch}'.")

    ctx.step("Are the dangerous paths ignored?")
    ctx.note("`git check-ignore -v <path>` answers yes or no, and names the .gitignore rule responsible.")
    problems = 0
    for path, why in MUST_BE_IGNORED:
        result = git("check-ignore", "-v", path)
        if result.returncode == 0:
            rule = result.stdout.split("\t")[0]  # e.g. ".gitignore:2:.env"
            ctx.note(f"  ignored      {path:<14} by {rule:<26} ({why})")
        else:
            problems += 1
            ctx.note(f"  NOT IGNORED  {path:<14} add it to .gitignore ({why})")

    ctx.step("Is anything secret already tracked?")
    ctx.note(".gitignore only stops NEW files being added. A file committed earlier stays tracked.")
    tracked = set(git("ls-files").stdout.splitlines())
    leaked = sorted(name for name in tracked if name == ".env" or (name.startswith(".env.") and name != ".env.example"))
    if leaked:
        problems += len(leaked)
        ctx.note("  TRACKED: " + ", ".join(leaked))
        ctx.note("  Stop tracking with `git rm --cached <file>`, and treat any key inside as leaked: revoke it.")
    else:
        ctx.note("  No .env file is tracked.")
    for name in MUST_BE_TRACKED:
        state = "tracked" if name in tracked else "not tracked (it should be committed)"
        ctx.note(f"  {name:<16} {state}")

    ctx.step("Verdict")
    if problems:
        ctx.note(f"{problems} thing(s) to fix before you push.")
    else:
        ctx.note("Safe to push: secrets and local clutter are ignored, and the files others need are tracked.")
    ctx.note("Run this in your own projects too: copy the script and edit the two lists at the top.")


if __name__ == "__main__":
    main()
