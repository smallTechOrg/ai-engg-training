"""20.4/3  The final check: is the project ready to hand over?

A last, mostly automatic review of the project folder, the same one a reviewer would do first:

  automatic   README with the required sections and no TODO left, architecture doc with all sections,
              every tool and environment variable mentioned in the README, evaluation set passes,
              Dockerfile runs as non-root, no key-shaped string anywhere, .env not committed;
  manual      things only you can judge, printed as a short list to tick off.

project/README.md is the finished README of the worked example: the generated parts from 20.4/1 plus
hand-written words in place of its TODO blocks. Copy the project, empty the README or leave a TODO in it,
and watch this check fail: that is how it protects you.

Run it:   ./run 20.4/3          (Windows: run 20.4/3)
"""

import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "project"))

from larkspur_desk import Desk, KnowledgeBase, TicketStore  # noqa: E402
from larkspur_desk.tools import TOOL_SPECS  # noqa: E402

from labkit import lesson  # noqa: E402

PROJECT = Path(__file__).parent / "project"
README_SECTIONS = ["How it works", "Knowledge base", "Tools", "Guardrails", "Run it", "HTTP API", "Configuration", "Known limitations"]
ARCH_SECTIONS = ["Problem", "Users", "Success criteria", "Non-goals", "Data sources", "Architecture", "Components",
                 "Risks and guardrails", "Cost and latency budget", "Evaluation plan", "Deployment", "Open questions"]
KEY_SHAPES = re.compile(r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY)")
MANUAL = [
    "A teammate who has not seen the project can run it from the README in under ten minutes.",
    "The README says what the assistant does NOT do.",
    "You have timed the demo and it fits in five minutes.",
    "You can say, in one sentence each, why you chose retrieval, a graph, these tools and these guardrails.",
    "You know the next two things you would fix, and they are written down.",
]


def headings(text):
    return set(re.findall(r"^##\s+(.*?)\s*$", text, re.M))


def checks(readme_text):
    results = []

    def add(name, ok, detail=""):
        results.append((name, ok, detail))

    missing = [s for s in README_SECTIONS if s not in headings(readme_text)]
    add("README has the required sections", not missing, f"missing: {missing}" if missing else "")
    add("README has no TODO left", "TODO" not in readme_text, f"{readme_text.count('TODO')} TODO block(s)" if "TODO" in readme_text else "")
    names = [spec["function"]["name"] for spec in TOOL_SPECS]
    absent = [n for n in names if n not in readme_text]
    add("README names every tool", not absent, f"missing: {absent}" if absent else "")
    env = re.findall(r"^([A-Z_]+)=", (PROJECT / ".env.example").read_text(encoding="utf-8"), re.M)
    absent = [n for n in env if n not in readme_text]
    add("README lists every environment variable", not absent, f"missing: {absent}" if absent else "")
    arch = (PROJECT / "docs" / "architecture.md").read_text(encoding="utf-8")
    missing = [s for s in ARCH_SECTIONS if s not in headings(arch)]
    add("docs/architecture.md has all 12 sections", not missing, f"missing: {missing}" if missing else "")
    desk = Desk(KnowledgeBase(PROJECT / "kb"), TicketStore())
    cases = json.loads((PROJECT / "evalset.json").read_text(encoding="utf-8"))
    good = 0
    for case in cases:
        result = desk.ask(case["q"])
        good += result.route == case["expect_route"] and (not case["expect_source"] or case["expect_source"] in result.sources)
    add("evaluation set: at least 8 of 10 as expected", good >= 8, f"{good} of {len(cases)}")
    dockerfile = (PROJECT / "Dockerfile").read_text(encoding="utf-8")
    add("Dockerfile runs as a non-root user", bool(re.search(r"^USER\s+(?!root)\S+", dockerfile, re.M)))
    leaks = [str(p.relative_to(PROJECT)) for p in PROJECT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".py", ".md", ".txt", ".json", ".example", ""}
             and KEY_SHAPES.search(p.read_text(encoding="utf-8", errors="ignore"))]
    add("no key-shaped string in the project", not leaks, f"in: {leaks}" if leaks else "")
    add(".env is not in the project folder", not (PROJECT / ".env").exists())
    return results


@lesson("20.4/3", "The final check: is the project ready to hand over?")
def main(ctx):
    ctx.step("Load the README")
    readme_path = PROJECT / "README.md"
    if readme_path.exists():
        text = readme_path.read_text(encoding="utf-8")
        ctx.note(f"read project/README.md ({len(text.splitlines())} lines)")
    else:
        text = ""
        ctx.note("project/README.md does not exist: run ./run 20.4/1 --write, edit the result and save it as README.md")

    ctx.step("Automatic checks")
    results = checks(text)
    for name, ok, detail in results:
        ctx.note(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    failed = [r for r in results if not r[1]]

    ctx.step("Manual checks: tick these off yourself")
    for item in MANUAL:
        ctx.note("[ ] " + item)

    ctx.step("Result")
    ctx.note(f"{len(results) - len(failed)} of {len(results)} automatic checks passed")
    if failed:
        ctx.note("Not ready yet: fix the FAIL lines above, then rerun.")
        sys.exit(1)
    ctx.note("Ready for the manual checks. Then present it.")


if __name__ == "__main__":
    main()
