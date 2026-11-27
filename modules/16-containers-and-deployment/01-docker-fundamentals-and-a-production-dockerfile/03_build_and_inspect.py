"""16.1/3  Inspect Docker and the compose file (read-only), and get the exact commands

Needs a running Docker engine. This script NEVER builds or runs anything: it runs
`docker version` and `docker compose config` (which only prints the resolved file) and
prints the commands you run yourself.

Run it:   ./run 16.1/3          (Windows: run 16.1/3)
"""

import shutil
import subprocess
from pathlib import Path

from labkit import lesson
from labkit.services import require

HERE = Path(__file__).parent


def docker(*args: str) -> str:
    exe = shutil.which("docker")
    done = subprocess.run([exe, *args], capture_output=True, text=True, timeout=30, cwd=HERE)
    return (done.stdout if done.returncode == 0 else done.stdout + done.stderr).strip()


@lesson("16.1/3", "Inspect Docker and the compose file")
def main(ctx):
    require("DOCKER")

    ctx.step("docker version")
    print(docker("version", "--format", "client {{.Client.Version}} / server {{.Server.Version}}"))

    ctx.step("docker compose config (the resolved compose file)")
    ctx.note("Needs a .env next to docker-compose.yml (copy .env.example). Values are not shown by this lesson.")
    if not (HERE / ".env").exists():
        print("No .env yet: run  cp .env.example .env  in the lesson folder, then run again.")
    else:
        print(docker("compose", "config", "--no-interpolate", "--quiet") or "compose file is valid")

    ctx.step("Commands for you to run (this script never runs them)")
    print(f"cd {HERE.name}")
    print("docker compose build")
    print("docker compose up -d")
    print("curl http://127.0.0.1:8000/health")
    print("docker compose ps        # shows (healthy) after the first check")
    print("docker compose down")


if __name__ == "__main__":
    main()
