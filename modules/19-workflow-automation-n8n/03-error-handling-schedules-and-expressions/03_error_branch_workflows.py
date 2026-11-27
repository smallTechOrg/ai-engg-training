"""19.3/3  Validate the digest and error workflows structurally

Two exported workflows ship here: a weekday digest (Schedule Trigger -> HTTP Request with an error output ->
IF -> Set) and an error workflow (Error Trigger -> alert). This script checks them without n8n: exactly one
trigger each, connections point at real nodes, the cron expression parses, the failure branch is on output 1
of a node whose onError is `continueErrorOutput`, every expression only refers to nodes that exist, and the
error workflow is the kind n8n can attach. A good CI test for hand-edited workflow JSON.

Run it:   ./run 19.3/3          (Windows: run 19.3/3)
     or:  python modules/19-workflow-automation-n8n/03-error-handling-schedules-and-expressions/03_error_branch_workflows.py
"""

import json
import re
from pathlib import Path

from labkit import lesson

HERE = Path(__file__).parent
TRIGGERS = ("scheduleTrigger", "webhook", "errorTrigger")
CRON_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]  # a compact check; script 1 has the full parser


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_in(v)


def check_cron(expr):
    parts = expr.split()
    if len(parts) != 5:
        return f"cron '{expr}' has {len(parts)} fields"
    for text, (low, high) in zip(parts, CRON_RANGES):
        for number in re.findall(r"\d+", text.split("/")[0]):
            if not low <= int(number) <= high:
                return f"cron '{expr}': {number} outside {low}-{high}"
    return None


def check(wf):
    problems, nodes = [], {n["name"]: n for n in wf["nodes"]}
    kinds = {name: n["type"].split(".")[-1] for name, n in nodes.items()}
    triggers = [name for name, k in kinds.items() if k in TRIGGERS]
    if len(triggers) != 1:
        problems.append(f"expected exactly 1 trigger, found {triggers}")
    for source, outputs in wf["connections"].items():
        if source not in nodes:
            problems.append(f"connection from missing node '{source}'")
        for branches in outputs.get("main", []):
            for link in branches:
                if link["node"] not in nodes:
                    problems.append(f"'{source}' connects to missing node '{link['node']}'")
    for name, node in nodes.items():
        outs = wf["connections"].get(name, {}).get("main", [])
        if node.get("onError") == "continueErrorOutput" and (len(outs) < 2 or not outs[1]):
            problems.append(f"'{name}' continues on error but nothing is wired to its error output (output 1)")
        if node.get("retryOnFail") and not 1 < node.get("maxTries", 3) <= 5:
            problems.append(f"'{name}': maxTries should be 2-5")
        if kinds[name] == "scheduleTrigger":
            for rule in node["parameters"]["rule"]["interval"]:
                if rule.get("field") == "cronExpression" and (msg := check_cron(rule["expression"])):
                    problems.append(msg)
        for text in strings_in(node["parameters"]):
            for ref in re.findall(r"\$\('([^']+)'\)", text):
                if ref not in nodes:
                    problems.append(f"'{name}': expression refers to unknown node '{ref}'")
            if text.startswith("=") and text.count("{{") != text.count("}}"):
                problems.append(f"'{name}': unbalanced braces in {text!r}")
    return problems, kinds, triggers


@lesson("19.3/3", "Validate the digest and error workflows")
def main(ctx):
    digest, error = load("helpdesk-digest-workflow.json"), load("helpdesk-error-workflow.json")
    for wf in (digest, error):
        ctx.step(f"Check '{wf['name']}'")
        problems, kinds, triggers = check(wf)
        for name, kind in kinds.items():
            node = next(n for n in wf["nodes"] if n["name"] == name)
            extras = [f"{k}={node[k]}" for k in ("retryOnFail", "maxTries", "waitBetweenTries", "onError") if k in node]
            print(f"  {name:<22} {kind:<16} {' '.join(extras)}")
        ctx.note(f"Trigger: {triggers}")
        print("  " + ("OK: no structural problems" if not problems else "\n  ".join("PROBLEM: " + p for p in problems)))

    ctx.step("How the two workflows are linked")
    setting = digest["settings"].get("errorWorkflow")
    ctx.note(f"digest settings.errorWorkflow = {setting!r}")
    ctx.note("Import the error workflow, copy its ID from the URL, and set it in the digest's Settings -> Error Workflow (or edit this key).")
    ctx.note("The error workflow only runs for ACTIVE or production executions that fail, not for manual test runs.")

    ctx.step("Prove the checker catches mistakes")
    broken = json.loads(json.dumps(digest))
    broken["connections"]["Fetch open tickets"]["main"] = broken["connections"]["Fetch open tickets"]["main"][:1]
    broken["nodes"][0]["parameters"]["rule"]["interval"][0]["expression"] = "0 25 * * 1-5"
    broken["nodes"][3]["parameters"]["assignments"]["assignments"][0]["value"] = "=Hi {{ $('Fetch tickets').item.json.open }}"
    for p in check(broken)[0]:
        print(f"  PROBLEM: {p}")


if __name__ == "__main__":
    main()
