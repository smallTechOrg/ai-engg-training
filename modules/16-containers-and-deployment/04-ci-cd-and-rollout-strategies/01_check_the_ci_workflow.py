"""16.4/1  A CI pipeline as a file: read and check the GitHub Actions workflow offline

CI/CD (continuous integration / delivery) runs your tests and builds and publishes the image on
every change, so releases are boring. ci-workflow.yml is a GitHub Actions workflow for the helpdesk
API: TEST, then BUILD, then PUSH to a registry, then a canary deploy. It would live in
.github/workflows/ of a real repository. This script cannot run GitHub Actions; it parses the file
and checks the properties that matter, first on the shipped workflow and then on a careless one.
No model call, no network.

Run it:   ./run 16.4/1          (Windows: run 16.4/1)
"""

import json
import re
from pathlib import Path

from labkit import lesson

WORKFLOW = Path(__file__).with_name("ci-workflow.yml")


def parse_yaml(text: str):
    """A small YAML reader for the subset compose and workflow files use: maps, lists, quoted
    and plain scalars, one-line [a, b] / {} values and `|` blocks. Real projects use PyYAML."""
    blocks: list[str] = []
    items: list[tuple[int, str]] = []
    raw = text.splitlines()
    i = 0
    while i < len(raw):
        line = raw[i].rstrip()
        i += 1
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()
        if body.endswith((": |", ": >", ": |-", ": >-")):
            parent, text_lines = indent, []
            while i < len(raw) and (not raw[i].strip() or len(raw[i]) - len(raw[i].lstrip()) > parent):
                text_lines.append(raw[i].strip())
                i += 1
            blocks.append("\n".join(text_lines).strip())
            body = body.rsplit(":", 1)[0] + f": @@{len(blocks) - 1}"
        items.append((indent, body))

    def scalar(value: str):
        value = value.strip()
        if value.startswith("@@"):
            return blocks[int(value[2:])]
        if value[:1] == "[" and value[-1:] == "]":
            inner = value[1:-1].strip()
            parts = re.findall(r"""\s*("[^"]*"|'[^']*'|[^,]+)\s*(?:,|$)""", inner)
            return [scalar(part) for part in parts]
        if value == "{}":
            return {}
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            return value[1:-1]
        if value.isdigit():
            return int(value)
        return {"true": True, "false": False}.get(value, value)

    def split_key(body: str):
        found = re.match(r"""^("[^"]*"|'[^']*'|[^\s"'\[{\-][^:]*?):(?:\s+(.*))?$""", body)
        return (found.group(1).strip("\"'"), found.group(2) or "") if found else None

    def parse(pos: int, indent: int):
        if items[pos][1].startswith("- "):
            result = []
            while pos < len(items) and items[pos][0] == indent and items[pos][1].startswith("- "):
                rest = items[pos][1][2:].strip()
                if split_key(rest):
                    items[pos] = (indent + 2, rest)
                    value, pos = parse(pos, indent + 2)
                else:
                    value, pos = scalar(rest), pos + 1
                result.append(value)
            return result, pos
        result = {}
        while pos < len(items) and items[pos][0] == indent and not items[pos][1].startswith("- "):
            key, value = split_key(items[pos][1]) or (items[pos][1], "")
            pos += 1
            if value:
                result[key] = scalar(value)
            elif pos < len(items) and (items[pos][0] > indent or (items[pos][0] == indent and items[pos][1].startswith("- "))):
                result[key], pos = parse(pos, items[pos][0])
            else:
                result[key] = None
        return result, pos

    return parse(0, items[0][0])[0] if items else {}


def job_order(jobs: dict) -> list[list[str]]:
    needs = {name: set(([job["needs"]] if isinstance(job.get("needs"), str) else job.get("needs")) or []) for name, job in jobs.items()}
    waves, done = [], set()
    while len(done) < len(needs):
        wave = sorted(n for n in needs if n not in done and needs[n] <= done)
        if not wave:
            raise ValueError("circular needs")
        waves.append(wave)
        done |= set(wave)
    return waves


def check(workflow: dict) -> list[str]:
    found = []
    jobs = workflow.get("jobs") or {}
    triggers = workflow.get("on") or {}
    if not jobs:
        return ["no jobs"]
    if "pull_request" not in triggers:
        found.append("does not run on pull requests: broken code is found only after merging")
    if "permissions" not in workflow:
        found.append("no top-level permissions: the token gets broad default rights (set contents: read)")
    for name, job in jobs.items():
        if "timeout-minutes" not in job:
            found.append(f"job {name}: no timeout-minutes (a hung job burns minutes for hours)")
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if uses and "@" not in uses:
                found.append(f"job {name}: {uses} is not pinned to a version")
            if uses.endswith(("@main", "@master", "@latest")):
                found.append(f"job {name}: {uses} follows a moving branch")
            text = json.dumps(step)
            if re.search(r"(sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,})", text):
                found.append(f"job {name}: a secret is written in the file; use ${{{{ secrets.NAME }}}}")
    names = " ".join(jobs)
    if "test" not in names:
        found.append("no test job")
    build = next((job for name, job in jobs.items() if "build" in name), None)
    if build is not None and "test" in names and "test" not in str(build.get("needs", "")):
        found.append("build does not need the test job: an untested image can be pushed")
    for name, job in jobs.items():
        for step in job.get("steps", []):
            if "build-push" in step.get("uses", "") and "pull_request" in triggers and "pull_request" not in str(step.get("with", {}).get("push", "")):
                found.append(f"job {name}: pushes images on pull requests (gate push with github.event_name != 'pull_request')")
    return found


@lesson("16.4/1", "Read and check a CI workflow")
def main(ctx):
    workflow = parse_yaml(WORKFLOW.read_text(encoding="utf-8"))

    ctx.step("The pipeline in ci-workflow.yml")
    print("  triggers:", ", ".join(f"{k} {v.get('branches', v.get('tags', ''))}" for k, v in workflow["on"].items()))
    for number, wave in enumerate(job_order(workflow["jobs"]), 1):
        for name in wave:
            job = workflow["jobs"][name]
            steps = [s.get("name") or s.get("uses") for s in job["steps"]]
            print(f"  stage {number}: {name:<14} runs on {job['runs-on']}; steps: {'; '.join(steps)}")
    ctx.note("'needs' makes a stage wait for the one before it. If test fails, build and deploy never start.")

    ctx.step("Checks on the shipped workflow")
    found = check(workflow)
    print("  all checks pass" if not found else "\n".join(f"  FAIL {item}" for item in found))

    ctx.step("The same checks on a careless workflow (embedded)")
    careless = parse_yaml(
        "name: x\non:\n  push:\n    branches: [main]\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - uses: actions/checkout\n      - uses: some/action@main\n"
        "      - run: docker login -u me -p ghp_abcdefgh12345678\n"
    )
    for item in check(careless):
        print(f"  FAIL {item}")

    ctx.step("What a real pipeline adds")
    print("  - Tests run against a stub model, never the paid endpoint: fast, free and deterministic (the course tests do this).")
    print("  - Provider keys live in GitHub Secrets (${{ secrets.NAME }}), never in the file or the image.")
    print("  - Tag images with the commit SHA; 'latest' cannot be rolled back to.")
    print("  - Offline evals (module 10) can be a job that blocks the deploy when quality drops.")


if __name__ == "__main__":
    main()
