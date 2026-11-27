"""00.3/1  What a .env file is, and who wins

A .env file is a plain text file of NAME=value lines. A library (python-dotenv) copies
those lines into the process's environment variables, where any code can read them.
This script builds a throwaway .env in a temporary folder, so your real one is never
touched, and shows the rule that surprises people: a variable that is already set wins
over the file. No model calls.

Run it:   ./run 00.3/1          (Windows: run 00.3/1)
     or:  python modules/00-setup/03-secrets-and-configuration-with-env/01_dotenv_basics.py
"""

import os
import tempfile
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from labkit import lesson

SAMPLE = """# Lines starting with # are comments.
DEMO_BASE_URL=https://your-provider.example/v1
DEMO_MODEL=small-model
DEMO_TIMEOUT=30
DEMO_GREETING="quotes are optional, and removed"
"""

DEMO_NAMES = ("DEMO_BASE_URL", "DEMO_MODEL", "DEMO_TIMEOUT", "DEMO_GREETING")


def demo_environment() -> dict:
    return {name: os.environ.get(name, "(not set)") for name in DEMO_NAMES}


@lesson("00.3/1", "What a .env file is, and who wins")
def main(ctx):
    with tempfile.TemporaryDirectory() as folder:
        env_file = Path(folder) / ".env"
        env_file.write_text(SAMPLE, encoding="utf-8")

        ctx.step("A .env file is just text")
        ctx.note("This sample was written to a temporary folder. Your real .env is not involved.")
        for line in SAMPLE.splitlines():
            ctx.note("    " + line)

        ctx.step("Read it without changing anything")
        ctx.note("dotenv_values() parses the file into a dictionary. Every value is a string, even 30.")
        ctx.show_data("dotenv_values(env_file)", dict(dotenv_values(env_file)))

        ctx.step("Load it into the environment")
        ctx.show_data("Before load_dotenv()", demo_environment())
        load_dotenv(env_file)
        ctx.show_data("After load_dotenv()", demo_environment())
        ctx.note("Now any code in this process can read os.environ['DEMO_MODEL'], without knowing a file exists.")

        ctx.step("Who wins: the file or a variable that is already set?")
        os.environ["DEMO_MODEL"] = "set-in-the-terminal"
        load_dotenv(env_file)  # the default: override=False
        ctx.note(f"Variable already set, then load_dotenv(env_file):                DEMO_MODEL = {os.environ['DEMO_MODEL']}")
        load_dotenv(env_file, override=True)
        ctx.note(f"Variable already set, then load_dotenv(env_file, override=True): DEMO_MODEL = {os.environ['DEMO_MODEL']}")
        ctx.note("By default the existing variable wins. That is how servers and CI override a .env without editing it,")
        ctx.note("and it is the first thing to check when 'I changed .env and nothing happened'.")

        ctx.step("Values are strings: convert them yourself")
        timeout = os.environ["DEMO_TIMEOUT"]
        ctx.show_data("DEMO_TIMEOUT", {"raw value": timeout, "type": type(timeout).__name__, "after float()": float(timeout)})

    for name in DEMO_NAMES:  # leave the environment as we found it
        os.environ.pop(name, None)
    ctx.note("The temporary folder is deleted and the DEMO_ variables are removed again.")


if __name__ == "__main__":
    main()
