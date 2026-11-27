"""20.4/1  Generate the README and architecture summary from the project itself

Documentation that is typed by hand drifts. This script reads the project in `project/` and builds the
parts of a README that can be derived from the code, so they are true by construction:

  - the graph diagram: parsed with `ast` from the node functions in graph.py (every `return "next"`);
  - the tools: names, descriptions and parameters from TOOL_SPECS;
  - the guardrails: the limits and patterns in guardrails.py;
  - the knowledge base: the pages and their status;
  - the HTTP endpoints and the environment variables (from app.py and .env.example).

The words around them (problem, decisions, limitations) are yours: the script leaves clearly marked
TODO blocks for those, and 20.4/3 refuses to pass while any remain. By default the result is printed and
written to a temp folder. Pass --write to save it as project/README.generated.md in this lesson folder
(project/README.md is the finished, hand-completed version that 20.4/3 checks; yours would replace it).

Run it:   ./run 20.4/1          (Windows: run 20.4/1)
"""

import ast
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "project"))

from larkspur_desk import guardrails  # noqa: E402
from larkspur_desk.tools import TOOL_SPECS  # noqa: E402

from labkit import lesson  # noqa: E402

PROJECT = Path(__file__).parent / "project"
NODES = ["guard", "retrieve", "decide", "answer", "check", "handover", "finish"]


def graph_edges(source):
    """{node: [possible next nodes]} read from the Desk class: string constants in `return` statements."""
    edges = {}
    for cls in [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ClassDef) and n.name == "Desk"]:
        for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in NODES]:
            targets = []
            for ret in [n for n in ast.walk(fn) if isinstance(n, ast.Return)]:
                if isinstance(ret.value, ast.Constant) and isinstance(ret.value.value, str) and ret.value.value not in targets:
                    targets.append(ret.value.value)
            edges[fn.name] = targets
    return edges


def mermaid(edges):
    lines = ["flowchart LR"]
    for node, targets in edges.items():
        for target in targets:
            lines.append(f"    {node} --> {target}")
    return "\n".join(lines)


def tool_table():
    rows = ["| Tool | What it does | Arguments |", "|---|---|---|"]
    for spec in TOOL_SPECS:
        fn = spec["function"]
        args = ", ".join(f"`{name}`" for name in fn["parameters"].get("properties", {}))
        rows.append(f"| `{fn['name']}` | {fn['description']} | {args} |")
    return "\n".join(rows)


def guardrail_list():
    return "\n".join([
        f"- Questions longer than {guardrails.MAX_QUESTION_CHARS} characters or empty are refused.",
        f"- {len(guardrails.INJECTION)} prompt-injection patterns are blocked before retrieval.",
        "- Email addresses and phone numbers are masked before any model or tool sees the text.",
        "- Answers must cite a known source id (or come from a tool) and may not contain secret-shaped strings.",
    ])


def kb_list():
    rows = []
    for path in sorted((PROJECT / "kb").glob("*.md")):
        header = path.read_text(encoding="utf-8").partition("\n\n")[0]
        meta = dict(line.split(": ", 1) for line in header.splitlines() if ": " in line)
        rows.append(f"- `{meta['id']}`: {meta['title']} ({meta['status']}, effective {meta['effective']})")
    return "\n".join(rows)


def env_vars():
    names = re.findall(r"^([A-Z_]+)=", (PROJECT / ".env.example").read_text(encoding="utf-8"), re.M)
    return "\n".join(f"- `{name}`" for name in names)


def endpoints():
    doc = ast.get_docstring(ast.parse((PROJECT / "app.py").read_text(encoding="utf-8"))) or ""
    return "\n".join(f"- `{line.strip()}`" for line in doc.splitlines() if line.strip().startswith(("POST", "GET")))


def build_readme():
    edges = graph_edges((PROJECT / "larkspur_desk" / "graph.py").read_text(encoding="utf-8"))
    return f"""# Larkspur desk

TODO: one paragraph on the problem this solves and for whom (copy it from docs/architecture.md).

## How it works

```mermaid
{mermaid(edges)}
```

TODO: two sentences on what each route (answered, handover, blocked) means for the user.

## Knowledge base

{kb_list()}

## Tools

{tool_table()}

## Guardrails

{guardrail_list()}

## Run it

- Offline, no model: `python app.py` (set nothing).
- With a model: set the variables below, then `python app.py`.
- Container: `docker build -t desk .` then `docker run -p 8080:8080 --env-file .env desk` (not run on the author's machine).

## HTTP API

{endpoints()}

## Configuration

{env_vars()}

## Known limitations

TODO: three honest limitations (for example: lexical search, one language, in-memory tickets).
"""


@lesson("20.4/1", "Generate the README and architecture summary from the project")
def main(ctx):
    ctx.step("Read the graph from the code and draw it")
    edges = graph_edges((PROJECT / "larkspur_desk" / "graph.py").read_text(encoding="utf-8"))
    for node, targets in edges.items():
        ctx.note(f"{node:9s} -> {', '.join(targets) or '(end)'}")

    ctx.step("Assemble the README")
    readme = build_readme()
    ctx.note(f"{len(readme.splitlines())} lines; {readme.count('TODO')} TODO block(s) left for you to write")
    for line in readme.splitlines()[:46]:
        ctx.note("    " + line)
    ctx.note("    ...")

    ctx.step("Save it")
    if "--write" in sys.argv:
        target = PROJECT / "README.generated.md"
        ctx.note(f"--write: saving {target.relative_to(PROJECT.parent)}")
    else:
        target = Path(tempfile.mkdtemp(prefix="desk-docs-")) / "README.md"
        ctx.note("saved to a temp folder (use --write to save into project/README.generated.md)")
    target.write_text(readme, encoding="utf-8")

    ctx.step("Your turn")
    ctx.note("Change a node's return value in graph.py and rerun: the diagram follows. Then replace the TODO blocks with your own words.")


if __name__ == "__main__":
    main()
