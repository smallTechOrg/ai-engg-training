"""09.5/1  Capstone, part 1: the change-request graph with an approval gate

Larkspur Labs employees file change requests ("open port 8443 on the staging firewall").
The graph: assess risk (a model call, with a rule floor the model cannot lower) ->
LOW risk is applied at once; anything else pauses for a human approval -> apply or refuse
-> notify the requester. Three requests run with scripted approvers. State lives in an
in-memory checkpointer here; part 2 makes it survive a restart.

Run it:   ./run 09.5/1          (Windows: run 09.5/1)
"""

import operator
from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
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


REQUESTS = [
    ("CR-101", "Increase the mailbox quota of one employee from 10 GB to 15 GB."),
    ("CR-102", "Delete the old staging database and its backups from production storage."),
    ("CR-103", "Add a new printer driver to the Larkspur Labs software catalogue."),
]
APPROVER_SAYS = {"CR-101": True, "CR-102": False, "CR-103": True}  # scripted decisions, used only if the graph pauses


@lesson("09.5/1", "Change-request graph with an approval gate")
def main(ctx):
    assess_risk, write_notice = make_model_functions(ctx)
    graph = build_graph(assess_risk, write_notice, InMemorySaver())

    ctx.step("Structure")
    ctx.note("nodes: " + ", ".join(n for n in graph.get_graph().nodes if not n.startswith("__")))

    for cr_id, text in REQUESTS:
        ctx.step(f"{cr_id}: {text[:60]}")
        config = {"configurable": {"thread_id": cr_id}}
        result = graph.invoke(new_cr(cr_id, text), config)
        if "__interrupt__" in result:
            ask = result["__interrupt__"][0].value
            ctx.note(f"PAUSED for approval, risk {ask['risk']}. Model's reason: {ask['reason'][:80]}")
            decision = {"approve": APPROVER_SAYS[cr_id], "by": "scripted approver"}
            ctx.note(f"approver decision: {decision}")
            result = graph.invoke(Command(resume=decision), config)
        else:
            ctx.note("no pause: LOW risk goes straight to apply")
        for line in result["audit"]:
            ctx.note(f"  audit | {line}")

    ctx.step("What to notice")
    ctx.note("The rule floor means a request containing 'delete' or 'production' is HIGH even if the model says LOW.")
    ctx.note("Unparseable model output counts as HIGH: the gate fails safe.")


if __name__ == "__main__":
    main()
