"""19.1/1  Anatomy of an n8n workflow

An n8n workflow is just a JSON document: nodes, plus a `connections` map from node name to node name.
This script loads the exported helpdesk workflow with plain Python, lists the parts, draws the graph
and runs a few sanity checks. No n8n and no model needed.

Run it:   ./run 19.1/1          (Windows: run 19.1/1)
     or:  python modules/19-workflow-automation-n8n/01-n8n-concepts/01_workflow_anatomy.py
"""

import json
import re
from pathlib import Path

from labkit import lesson

WORKFLOW = Path(__file__).with_name("helpdesk-ticket-workflow.json")
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\"?\s*[:=]\s*\"[^\"{=]{8,}\""),
]


def strings_in(value):
    """Yield every string inside nested JSON."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_in(v)


@lesson("19.1/1", "Anatomy of an n8n workflow")
def main(ctx):
    ctx.step("Load the workflow file")
    wf = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    nodes = {n["name"]: n for n in wf["nodes"]}
    ctx.note(f"Workflow '{wf['name']}': {len(nodes)} nodes, top-level keys {sorted(wf)}")

    ctx.step("List the nodes")
    ctx.note("Every node has an id, a name, a type, a typeVersion, a canvas position and parameters.")
    for n in wf["nodes"]:
        kind = n["type"].split(".")[-1]
        print(f"  {n['name']:<18} type={kind:<18} v{n['typeVersion']:<4} at {n['position']}")

    ctx.step("Find the trigger")
    triggers = [n for n in wf["nodes"] if n["type"].lower().endswith(("trigger", ".webhook"))]
    for t in triggers:
        p = t["parameters"]
        ctx.note(f"Trigger: {t['name']} ({t['type']}) listens for {p.get('httpMethod')} /webhook/{p.get('path')}")
    if len(triggers) != 1:
        ctx.note(f"Expected exactly one trigger, found {len(triggers)}.")

    ctx.step("Walk the connections as a graph")
    ctx.note("`connections` is keyed by SOURCE node name; each output is a list of lists of targets.")
    edges = []
    for source, outputs in wf["connections"].items():
        for output_name, branches in outputs.items():
            for branch_no, targets in enumerate(branches):
                for t in targets:
                    edges.append((source, t["node"], output_name, branch_no))
    for a, b, out, branch in edges:
        print(f"  {a}  --[{out}#{branch}]-->  {b}")

    ctx.note("Order of execution, following the edges from the trigger:")
    order, current, seen = [], triggers[0]["name"] if triggers else None, set()
    while current and current not in seen:
        order.append(current)
        seen.add(current)
        current = next((b for a, b, _, _ in edges if a == current), None)
    print("  " + " -> ".join(order))

    ctx.step("Mermaid diagram (paste into any Mermaid viewer)")
    ids = {name: f"n{i}" for i, name in enumerate(nodes)}
    print("  flowchart LR")
    for name, ident in ids.items():
        print(f'    {ident}["{name}"]')
    for a, b, _, _ in edges:
        print(f"    {ids[a]} --> {ids[b]}")

    ctx.step("Check the file")
    problems = []
    for a, b, _, _ in edges:
        for name in (a, b):
            if name not in nodes:
                problems.append(f"dangling connection: '{name}' is not a node")
    unreachable = set(nodes) - set(order)
    for name in sorted(unreachable):
        problems.append(f"node '{name}' is not reachable from the trigger")
    for n in wf["nodes"]:
        for s in strings_in(n["parameters"]):
            if any(p.search(f'"x": "{s}"') or p.search(s) for p in SECRET_PATTERNS):
                problems.append(f"secret-looking string in node '{n['name']}'")
        for cred in n.get("credentials", {}).values():
            ctx.note(f"'{n['name']}' references credential '{cred['name']}' by name only (secret lives in n8n)")
    if problems:
        for p in problems:
            print(f"  PROBLEM: {p}")
    else:
        ctx.note("No dangling connections, no unreachable nodes, no secret-looking strings.")


if __name__ == "__main__":
    main()
