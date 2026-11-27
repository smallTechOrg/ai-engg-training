"""16.5/1  Capstone, part 1: audit the stack against the acceptance criteria

The brief (see the README) lists what a production-ready helpdesk stack must satisfy. This script
checks the files in this folder (docker-compose.yml, Dockerfile, ci-workflow.yml, .gitignore,
.env.example, app/) against those criteria, offline, and prints a pass/fail line for each one.
Edit the files and run it again: it is your test while you work on the stretch goals.
No Docker, no network, no model.

Run it:   ./run 16.5/1          (Windows: run 16.5/1)
"""

import re
from pathlib import Path

from labkit import lesson

HERE = Path(__file__).parent
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)", re.I)


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


def read(name: str) -> str:
    path = HERE / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def criteria() -> list[tuple[str, bool, str]]:
    """(criterion, passed, detail)"""
    compose = parse_yaml(read("docker-compose.yml") or "services: {}")
    services = compose.get("services") or {}
    dockerfile = [line.strip() for line in read("Dockerfile").splitlines() if line.strip() and not line.strip().startswith("#")]
    workflow = parse_yaml(read("ci-workflow.yml") or "jobs: {}")
    out = []

    wanted = {"api", "worker", "redis", "chroma"}
    out.append(("1. Four services: api, worker, redis, chroma", wanted <= set(services), f"found {sorted(services)}"))

    unpinned = [n for n, s in services.items() if s.get("image") and (":" not in s["image"].split("/")[-1] or s["image"].endswith(":latest"))]
    out.append(("2. Every image pinned to a tag", not unpinned, f"unpinned: {unpinned}" if unpinned else "ok"))

    exposed = [f"{n}:{p}" for n, s in services.items() for p in s.get("ports", []) if not str(p).startswith("127.0.0.1:")]
    out.append(("3. Published ports bound to 127.0.0.1; redis not published", not exposed and "ports" not in services.get("redis", {}), f"exposed: {exposed}" if exposed else "ok"))

    literal = []
    for n, s in services.items():
        for key, value in (s.get("environment") or {}).items():
            if SECRET_NAME.search(key) and value and not str(value).startswith("${"):
                literal.append(f"{n}.{key}")
    uses_secret = "secrets" in compose and any("llm_api_key" in (s.get("secrets") or []) for s in services.values())
    out.append(("4. API key delivered as a Docker secret, none written in the file", uses_secret and not literal, f"literal: {literal}" if literal else ("ok" if uses_secret else "no secrets: section used")))

    missing = [n for n in ("api", "worker", "redis") if "healthcheck" not in services.get(n, {})]
    out.append(("5. Healthchecks on api, worker and redis", not missing, f"missing: {missing}" if missing else "ok"))

    start = services.get("api", {}).get("depends_on") or {}
    out.append(("6. api waits for a HEALTHY redis (service_healthy)", isinstance(start, dict) and start.get("redis", {}).get("condition") == "service_healthy", "ok" if start else "no depends_on"))

    grace = [str(services.get(n, {}).get("stop_grace_period", "")) for n in ("api", "worker")]
    out.append(("7. Grace periods of at least 15 s for api and worker", all(g.endswith("s") and g[:-1].isdigit() and int(g[:-1]) >= 15 for g in grace), f"api/worker: {grace}"))

    out.append(("8. Restart policy and named volumes for redis and chroma", all("restart" in services.get(n, {}) and services.get(n, {}).get("volumes") for n in ("redis", "chroma")), "ok"))

    out.append(("9. Dockerfile: multi-stage, pinned base, non-root, HEALTHCHECK, exec-form CMD",
                sum(1 for line in dockerfile if line.upper().startswith("FROM ")) >= 2
                and not any(":latest" in line for line in dockerfile if line.upper().startswith("FROM "))
                and any(line.upper().startswith("USER ") for line in dockerfile)
                and any(line.upper().startswith("HEALTHCHECK ") for line in dockerfile)
                and any(line.startswith("CMD [") for line in dockerfile), "ok"))

    jobs = workflow.get("jobs") or {}
    out.append(("10. CI: test then build then deploy via needs; pushes skipped on pull requests",
                "test" in jobs and "test" in str(jobs.get("build", {}).get("needs", "")) and "pull_request" in read("ci-workflow.yml"), "ok"))

    out.append(("11. .env and secret files are git-ignored; .env.example has no real key",
                ".env" in read(".gitignore") and "secrets/*.txt" in read(".gitignore") and "replace-me" in read(".env.example"), "ok"))
    return out


@lesson("16.5/1", "Capstone: audit the stack")
def main(ctx):
    ctx.step("Acceptance criteria")
    results = criteria()
    for name, passed, detail in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name}" + ("" if passed or detail == "ok" else f"  ({detail})"))
    passed = sum(1 for _, ok, _ in results if ok)
    ctx.step("Result")
    print(f"  {passed} of {len(results)} criteria pass")
    if passed < len(results):
        ctx.note("Fix the FAIL lines in the files of this folder, then run this script again.")
    ctx.note("These are structure checks. They do not prove the stack runs: build and start it with the commands in the README when you have Docker.")


if __name__ == "__main__":
    main()
