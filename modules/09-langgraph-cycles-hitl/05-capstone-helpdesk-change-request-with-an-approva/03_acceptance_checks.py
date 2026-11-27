"""09.5/3  Capstone, part 3: acceptance checks for the gate

Tests of a graph's STRUCTURE should not depend on what a model happens to say. So the
risk assessor is replaced by a fake that returns whatever the check needs, and the checks
assert the invariants of the brief: no side effect without approval, a rejected request is
never applied, the rule floor beats the model, unclear model output fails safe, and a
paused request can be resumed from a fresh process. One live check at the end uses the real
model and only reports. No model calls are made for the checks themselves.

Run it:   ./run 09.5/3          (Windows: run 09.5/3)
"""

import operator
import tempfile
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from labkit import lesson

# ---- the change-request graph (the same block is copied into each capstone script) ----
RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
# A rule floor: whatever the model says, these words make a change at least HIGH.
HIGH_RISK_WORDS = ("production", "delete", "firewall", "all users", "admin")


class CR(TypedDict):
    cr_id: str
    text: str
    risk: str
    reason: str
    approval: str
    audit: Annotated[list[str], operator.add]


def rule_floor(text: str) -> str:
    return "HIGH" if any(w in text.lower() for w in HIGH_RISK_WORDS) else "LOW"


def parse_risk(raw: str) -> str:
    """Pick the first risk word in the model's answer; anything unclear counts as HIGH (fail safe)."""
    up = raw.upper()
    hits = sorted((up.find(k), k) for k in RISK_ORDER if k in up)
    return hits[0][1] if hits else "HIGH"


def build_graph(assess_risk, write_notice, saver):
    """assess_risk(text) -> (risk, reason); write_notice(state) -> str. Both are injected so
    script 3 can test the graph structure without a model."""

    def assess(state: CR) -> dict:
        model_risk, reason = assess_risk(state["text"])
        floor = rule_floor(state["text"])
        risk = max(model_risk, floor, key=RISK_ORDER.get)
        note = f"risk={risk} (model said {model_risk}, rule floor {floor})"
        return {"risk": risk, "reason": reason, "audit": [note]}

    def route_after_assess(state: CR) -> str:
        return "apply" if state["risk"] == "LOW" else "approval"

    def approval(state: CR) -> dict:
        decision = interrupt({"cr_id": state["cr_id"], "change": state["text"], "risk": state["risk"], "reason": state["reason"]})
        return {"approval": "approved" if decision.get("approve") else "rejected",
                "audit": [f"approval: {decision.get('by', '?')} -> {'approve' if decision.get('approve') else 'reject'}"]}

    def route_after_approval(state: CR) -> str:
        return "apply" if state["approval"] == "approved" else "notify"

    def apply(state: CR) -> dict:
        # The ONLY node with a side effect (here: an audit line). Reached from LOW or from an approval.
        return {"audit": [f"APPLIED {state['cr_id']}"]}

    def notify(state: CR) -> dict:
        return {"audit": [f"notice: {write_notice(state)}"]}

    g = StateGraph(CR)
    for name, fn in [("assess", assess), ("approval", approval), ("apply", apply), ("notify", notify)]:
        g.add_node(name, fn)
    g.add_edge(START, "assess")
    g.add_conditional_edges("assess", route_after_assess, ["apply", "approval"])
    g.add_conditional_edges("approval", route_after_approval, ["apply", "notify"])
    g.add_edge("apply", "notify")
    g.add_edge("notify", END)
    return g.compile(checkpointer=saver)


def new_cr(cr_id: str, text: str) -> CR:
    return {"cr_id": cr_id, "text": text, "risk": "", "reason": "", "approval": "", "audit": []}

def make_model_functions(ctx):
    """Two small model calls: a risk assessor and a notice writer."""
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    def assess_risk(text: str):
        ai = model.invoke([
            ("system", "You review IT change requests for Larkspur Labs. Start your answer with exactly one word, LOW, MEDIUM or HIGH, "
                       "then a colon and one short reason."),
            ("user", text),
        ])
        ctx.record_usage(ai.usage_metadata)
        raw = str(ai.content).strip()
        return parse_risk(raw), raw[:100]

    def write_notice(state: CR) -> str:
        outcome = "was applied" if any(a.startswith("APPLIED") for a in state["audit"]) else "was not applied"
        ai = model.invoke([
            ("system", "Write one short sentence telling the requester what happened to their change request."),
            ("user", f"Change request {state['cr_id']}: {state['text']}. It {outcome}."),
        ])
        ctx.record_usage(ai.usage_metadata)
        return str(ai.content).strip()[:110]

    return assess_risk, write_notice


def applied(state_or_result) -> bool:
    return any(a.startswith("APPLIED") for a in state_or_result["audit"])


@lesson("09.5/3", "Acceptance checks for the approval gate")
def main(ctx):
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        ctx.note(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")

    def fake(risk):
        return lambda text: (risk, f"fake says {risk}")

    notice = lambda s: "fake notice"

    ctx.step("Checks with a fake assessor (deterministic)")
    for label, risk, text, approve, want_applied, want_pause in [
        ("LOW risk is applied with no pause", "LOW", "Add a printer driver to the catalogue.", None, True, False),
        ("HIGH risk pauses, approve -> applied", "HIGH", "Rotate the shared service key.", True, True, True),
        ("HIGH risk pauses, reject -> NOT applied", "HIGH", "Rotate the shared service key.", False, False, True),
        ("model says LOW but text says production delete -> still pauses", "LOW", "Delete the old production share.", False, False, True),
    ]:
        graph = build_graph(fake(risk), notice, InMemorySaver())
        config = {"configurable": {"thread_id": label}}
        out = graph.invoke(new_cr("CR-T", text), config)
        paused = "__interrupt__" in out
        if paused:
            out = graph.invoke(Command(resume={"approve": approve, "by": "test"}), config)
        check(label, paused == want_pause and applied(out) == want_applied, f"(paused={paused}, applied={applied(out)})")

    check("unparseable model output fails safe", parse_risk("I am not sure what you mean") == "HIGH")
    check("parse_risk reads a plain 'low: tiny change'", parse_risk("low: tiny change") == "LOW")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = str(Path(tmp) / "t.sqlite")
        config = {"configurable": {"thread_id": "CR-T2"}}
        with SqliteSaver.from_conn_string(db) as saver:
            build_graph(fake("HIGH"), notice, saver).invoke(new_cr("CR-T2", "Rotate the shared service key."), config)
        with SqliteSaver.from_conn_string(db) as saver:
            graph = build_graph(fake("HIGH"), notice, saver)
            out = graph.invoke(Command(resume={"approve": True, "by": "test"}), config)
            check("resume from a fresh connection works", applied(out))

    ctx.step("One live look at the real model (informational, not a check)")
    assess_risk, _ = make_model_functions(ctx)
    for text in ("Add a printer driver to the catalogue.", "Delete the production customer database."):
        risk, reason = assess_risk(text)
        ctx.note(f"model risk for {text!r}: {risk}  | rule floor: {rule_floor(text)}")

    ctx.step("Summary")
    ctx.note(f"{sum(results)} of {len(results)} checks passed")
    if not all(results):
        raise SystemExit("an acceptance check failed")


if __name__ == "__main__":
    main()
