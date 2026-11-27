"""16.1/2  A read-only Dockerfile linter

Checks a Dockerfile against common production practices, in plain Python. It only READS files.
Runs on the shipped Dockerfile (should pass) and on a deliberately bad example (should not).
Real tools such as hadolint do this more thoroughly; this shows what they look for.

Run it:   ./run 16.1/2          (Windows: run 16.1/2)
"""

import re
from pathlib import Path

from labkit import lesson

HERE = Path(__file__).parent
SECRET_WORDS = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.I)

BAD = """FROM python:latest
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
ENV OPENAI_API_KEY=sk-not-a-real-key
EXPOSE 8000
CMD python app/main.py
"""


def instructions(text: str) -> list[tuple[str, str]]:
    out, buf = [], ""
    for raw in text.splitlines():
        line = raw.strip()
        if not buf and (not line or line.startswith("#")):
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        buf += line
        word, _, rest = buf.partition(" ")
        out.append((word.upper(), rest.strip()))
        buf = ""
    return out


def review(text: str, has_dockerignore: bool) -> list[str]:
    ins = instructions(text)
    problems = []
    froms = [a for i, a in ins if i == "FROM"]
    for a in froms:
        image = a.split()[0]
        if image in {"scratch"} or image.isidentifier() and image in {a2.split()[-1] for a2 in froms if " as " in a2.lower()}:
            continue
        tag = image.split(":", 1)[1] if ":" in image else ""
        if not tag or tag == "latest":
            problems.append(f"base image '{image}' is not pinned (no tag or :latest)")
    if len(froms) < 2:
        problems.append("single-stage build: build tools end up in the final image (use multi-stage)")
    users = [a for i, a in ins if i == "USER"]
    if not users or users[-1].split(":")[0] in {"root", "0"}:
        problems.append("no non-root USER: the container runs as root")
    if not any(i == "HEALTHCHECK" for i, _ in ins):
        problems.append("no HEALTHCHECK")
    for i, a in ins:
        if i in {"ENV", "ARG"} and SECRET_WORDS.search(a.split("=")[0].split()[0] if a else ""):
            problems.append(f"{i} with a secret-looking name ({a.split('=')[0].split()[0]}): inject secrets at runtime")
    if not has_dockerignore:
        problems.append("no .dockerignore: .env and .git can leak into the build context")
    seen_copy_all = False
    for i, a in ins:
        if i == "FROM":
            seen_copy_all = False
        if i == "COPY" and not a.startswith("--from") and any(p in {".", "./"} for p in a.split()[:-1]):
            seen_copy_all = True
        if i == "RUN" and ("install" in a or "sync" in a) and seen_copy_all:
            problems.append("COPY . before the dependency install: every code edit busts the dependency cache")
            break
    if not any(i == "CMD" and a.startswith("[") or i == "ENTRYPOINT" and a.startswith("[") for i, a in ins):
        problems.append("CMD/ENTRYPOINT not in exec form (JSON array): the shell becomes PID 1 and swallows SIGTERM")
    return problems


def report(ctx, title: str, text: str, ignore: bool) -> None:
    ctx.step(title)
    problems = review(text, ignore)
    if problems:
        print(f"{len(problems)} problem(s):")
        for p in problems:
            print("  FAIL", p)
    else:
        print("PASS: no problems found by the 8 checks.")


@lesson("16.1/2", "Dockerfile review")
def main(ctx):
    real = (HERE / "Dockerfile").read_text(encoding="utf-8")
    report(ctx, "The shipped Dockerfile", real, (HERE / ".dockerignore").exists())
    ctx.note("The next one is a deliberately bad example embedded in this script.")
    report(ctx, "A bad Dockerfile (embedded example)", BAD, False)
    ctx.note("Nothing was built or modified. Try breaking the shipped Dockerfile and re-running.")


if __name__ == "__main__":
    main()
