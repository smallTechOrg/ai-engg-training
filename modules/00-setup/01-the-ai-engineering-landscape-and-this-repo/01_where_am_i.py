"""00.1/1  Where am I?

A quick look at your computer and the course folder before you start. It prints which
Python is running, where the course lives on disk, and whether you have set up a model
endpoint (the web address of the AI model you will call). If you have, it ends with one
"hello" call to the model to prove that everything is connected.

Run it:   ./run 00.1/1          (Windows: run 00.1/1)
     or:  python modules/00-setup/01-the-ai-engineering-landscape-and-this-repo/01_where_am_i.py
"""

import platform
import sys

from labkit import lesson, repo_root
from labkit.config import mask

# The files and folders at the top of the repo that you will use.
LANDMARKS = [
    ("README.md", "start here: setup and everyday commands"),
    ("CURRICULUM.md", "the whole journey: every module and lesson, with status"),
    ("curriculum.toml", "the list CURRICULUM.md is generated from"),
    (".env", "YOUR settings: endpoint, key, model (never committed)"),
    (".env.example", "the template .env is copied from"),
    ("modules", "the lessons: one folder per module, one folder per lesson"),
    ("src/labkit", "shared plumbing: client, printing, logs, launcher, doctor"),
    ("tests", "checks that every ready lesson still runs"),
    ("logs", "a record of every lesson run (created on first run)"),
]


@lesson("00.1/1", "Where am I?")
def main(ctx):
    ctx.step("The machine and the Python running this script")
    ctx.show_data(
        "Environment",
        {
            "operating system": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "python version": platform.python_version(),
            "python executable": sys.executable,
        },
    )
    ctx.note("The executable should live inside this repo's .venv folder. Lesson 00.2 explains why.")

    ctx.step("The repo: what lives where")
    root = repo_root()
    ctx.note(f"Repo root: {root}")
    for name, purpose in LANDMARKS:
        found = "found  " if (root / name).exists() else "missing"
        ctx.note(f"  {found}  {name:<16} {purpose}")
    ctx.note("'missing' is normal for .env before setup and for logs before your first run.")

    ctx.step("The model endpoint")
    settings = ctx.settings
    missing = settings.missing()
    ctx.show_data(
        "Settings (the key is masked, never printed)",
        {
            "LLM_BASE_URL": settings.base_url or "(not set)",
            "LLM_MODEL": settings.model or "(not set)",
            "LLM_API_KEY": mask(settings.api_key),
        },
    )
    if missing:
        ctx.note("No endpoint configured yet: " + ", ".join(missing) + " not set.")
        ctx.note("That is fine for this lesson. Fill in .env before module 01 and check with: ./run doctor")
        return

    ctx.step("One hello to the model")
    ctx.note("This is the call the whole course is built on. Lesson 01.1 takes it apart.")
    messages = [{"role": "user", "content": "Say hello to a new AI engineering student in one short sentence."}]
    ctx.show_messages(messages)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    ctx.show_response(response)


if __name__ == "__main__":
    main()
