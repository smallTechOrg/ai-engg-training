"""20.1/2  Validate an architecture document for required sections

The design doc is the contract for the rest of the capstone. This script checks that a markdown
file has every required section, that sections are not empty or left as TODO, that the success
criteria contain numbers, that there is a mermaid diagram and at least three risks.

It checks the filled-in helpdesk example, the blank template (which must fail), and a copy of the
example with two sections damaged on purpose. Pass your own file as an argument:

    ./run 20.1/2 my-architecture.md       (exit code 1 when your file is not valid)

No model call.

Run it:   ./run 20.1/2          (Windows: run 20.1/2)
"""

import re
import sys
from pathlib import Path

from labkit import lesson

HERE = Path(__file__).parent
REQUIRED = [
    "Problem", "Users", "Success criteria", "Non-goals", "Data sources", "Architecture",
    "Components", "Risks and guardrails", "Cost and latency budget", "Evaluation plan",
    "Deployment", "Open questions",
]
MIN_WORDS = 12  # a section shorter than this is a placeholder, not a decision


def sections(text):
    """Map section title -> body, for every '## ' heading."""
    found = {}
    current = None
    for line in text.splitlines():
        match = re.match(r"##\s+(.*?)\s*$", line)
        if match:
            current = match.group(1)
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return {title: "\n".join(lines).strip() for title, lines in found.items()}


def check(text):
    """Return a list of plain-language problems; empty means valid."""
    problems = []
    body = sections(text)
    for name in REQUIRED:
        if name not in body:
            problems.append(f"missing section: {name}")
            continue
        content = body[name]
        if "TODO" in content or re.search(r"<[^>\n]+>", re.sub(r"```.*?```", "", content, flags=re.S)):
            problems.append(f"{name}: still has TODO or <placeholder> text")
        elif len(content.split()) < MIN_WORDS:
            problems.append(f"{name}: only {len(content.split())} words, say more (minimum {MIN_WORDS})")
    if "<" in text.splitlines()[0]:
        problems.append("title still has a <placeholder>")
    criteria = body.get("Success criteria", "")
    bullets = [line for line in criteria.splitlines() if line.lstrip().startswith("-")]
    if "Success criteria" in body and not all(re.search(r"\d", line) for line in bullets):
        problems.append("Success criteria: every bullet needs a number (a target you can measure)")
    if "Success criteria" in body and len(bullets) < 2:
        problems.append("Success criteria: list at least two targets")
    if "```mermaid" not in body.get("Architecture", ""):
        problems.append("Architecture: needs a ```mermaid diagram")
    risks = [line for line in body.get("Risks and guardrails", "").splitlines() if line.lstrip().startswith("-")]
    if "Risks and guardrails" in body and len(risks) < 3:
        problems.append(f"Risks and guardrails: {len(risks)} risk(s) listed, need at least 3")
    return problems


def report(ctx, name, text):
    problems = check(text)
    if problems:
        ctx.note(f"{name}: {len(problems)} problem(s)")
        for problem in problems[:6]:
            ctx.note(f"    - {problem}")
        if len(problems) > 6:
            ctx.note(f"    ... and {len(problems) - 6} more")
    else:
        ctx.note(f"{name}: valid ({len(REQUIRED)} required sections present)")
    return problems


@lesson("20.1/2", "Validate an architecture document for required sections")
def main(ctx):
    own = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    if own:
        ctx.step(f"Check your file: {own[0]}")
        path = Path(own[0])
        if not path.exists():
            ctx.note(f"No such file: {path}")
            raise SystemExit(2)
        problems = report(ctx, path.name, path.read_text(encoding="utf-8"))
        if problems:
            raise SystemExit(1)
        return

    ctx.step("The filled-in worked example")
    example = (HERE / "helpdesk-architecture.md").read_text(encoding="utf-8")
    ok = report(ctx, "helpdesk-architecture.md", example)

    ctx.step("The blank template (should fail until you fill it in)")
    report(ctx, "design-template.md", (HERE / "design-template.md").read_text(encoding="utf-8"))

    ctx.step("The example with two sections damaged on purpose")
    damaged = example.replace("## Evaluation plan", "## Tests").replace(
        "- At least 8 of 10 test questions answered with the right source id cited.", "- Answers should be good.")
    report(ctx, "damaged copy", damaged)

    ctx.step("Your turn")
    ctx.note("Copy design-template.md, fill it in, then: ./run 20.1/2 your-file.md")
    if ok:
        ctx.note("The worked example passes, so the checker itself works.")


if __name__ == "__main__":
    main()
