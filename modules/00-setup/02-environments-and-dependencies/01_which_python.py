"""00.2/1  Which Python is this?

"It works on my machine" problems usually start here: the script ran with a different
Python, or a different set of packages, than you expected. This script asks the Python
that is running it where it lives and whether it is inside a virtual environment. It makes
no model calls.

Run it:   ./run 00.2/1          (Windows: run 00.2/1)
     or:  python modules/00-setup/02-environments-and-dependencies/01_which_python.py
"""

import os
import platform
import sys
from pathlib import Path

from labkit import lesson, repo_root


@lesson("00.2/1", "Which Python is this?")
def main(ctx):
    ctx.step("Ask the interpreter who it is")
    ctx.show_data(
        "The running interpreter",
        {
            "sys.executable": sys.executable,
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
    )
    ctx.note("sys.executable is the Python really running. What `python` means in a terminal depends on PATH.")

    ctx.step("Is it a virtual environment?")
    ctx.note("A virtual environment is a folder with its own packages that borrows a Python installed elsewhere.")
    in_venv = sys.prefix != sys.base_prefix
    ctx.show_data(
        "Two prefixes",
        {
            "sys.prefix (where packages for THIS run live)": sys.prefix,
            "sys.base_prefix (the Python it was created from)": sys.base_prefix,
            "different, so this is a virtual environment": in_venv,
        },
    )
    if in_venv:
        ctx.note("They differ: packages installed here stay here and cannot break other projects.")
    else:
        ctx.note("They are the same: this is a system-wide Python. Packages installed here are shared by everything.")

    ctx.step("Is it THIS repo's environment?")
    expected = repo_root() / ".venv"
    here = Path(sys.prefix).resolve() == expected.resolve()
    ctx.show_data(
        "Comparison",
        {
            "this repo's environment": str(expected),
            "exists": expected.is_dir(),
            "the running Python is inside it": here,
            "VIRTUAL_ENV variable (set when a venv is 'activated')": os.environ.get("VIRTUAL_ENV", "(not set)"),
        },
    )
    if here:
        ctx.note("Yes. ./run and `uv run` always use this environment, whether or not it is activated.")
    else:
        ctx.note("No. You ran this with a different Python. Use ./run 00.2/1, or activate .venv first.")

    ctx.step("Where Python looks for packages")
    ctx.note("An `import` searches these folders in order. The first match wins.")
    for index, entry in enumerate(sys.path, 1):
        ctx.note(f"  {index}. {entry or '(the current folder)'}")


if __name__ == "__main__":
    main()
