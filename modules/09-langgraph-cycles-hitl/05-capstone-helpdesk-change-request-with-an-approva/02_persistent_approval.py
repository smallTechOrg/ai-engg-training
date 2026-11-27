"""09.5/2  Capstone, part 2: the approval survives a restart

Same graph, but the checkpointer is a SQLite file. Process 1 files a change request and
stops at the approval gate (the requester gets "waiting for approval"). The process
ends. Hours later, process 2 opens the same file with a NEW graph object, lists the
requests waiting for approval, and resumes the right one with the approver's decision.
The two "processes" are two with-blocks that each open and close their own connection.

Run it:   ./run 09.5/2          (Windows: run 09.5/2)
"""

import operator
import tempfile
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
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


@lesson("09.5/2", "Approval gate that survives a restart")
def main(ctx):
    assess_risk, write_notice = make_model_functions(ctx)
    cr = new_cr("CR-201", "Open firewall port 8443 for all users of the staging environment.")
    config = {"configurable": {"thread_id": cr["cr_id"]}}

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = str(Path(tmp) / "change-requests.sqlite")

        ctx.step("Process 1: file the request, stop at the gate")
        with SqliteSaver.from_conn_string(db) as saver:
            graph = build_graph(assess_risk, write_notice, saver)
            result = graph.invoke(cr, config)
            ctx.note(f"paused: {'__interrupt__' in result}; next node: {graph.get_state(config).next}")
            ctx.note(f"risk shown to the approver: {result['risk']}")
        ctx.note("process 1 exits here. Nothing is in memory; the request exists only in the SQLite file.")

        ctx.step("Process 2: find what is waiting, then decide")
        with SqliteSaver.from_conn_string(db) as saver:
            graph = build_graph(assess_risk, write_notice, saver)
            waiting = [t for t in ("CR-201",) if graph.get_state({"configurable": {"thread_id": t}}).next]
            ctx.note(f"requests waiting for approval: {waiting}")
            snap = graph.get_state(config)
            ctx.note(f"what the approver sees: {snap.tasks[0].interrupts[0].value['change']}")
            decision = {"approve": False, "by": "network-lead"}
            ctx.note(f"decision: {decision}")
            final = graph.invoke(Command(resume=decision), config)
            for line in final["audit"]:
                ctx.note(f"  audit | {line}")
            ctx.note(f"applied? {any(a.startswith('APPLIED') for a in final['audit'])}")

        ctx.step("Process 3: the decision is permanent")
        with SqliteSaver.from_conn_string(db) as saver:
            graph = build_graph(assess_risk, write_notice, saver)
            snap = graph.get_state(config)
            ctx.note(f"next nodes: {snap.next} (empty: finished), approval = {snap.values['approval']}")

    ctx.note("A real deployment keeps the file on a volume (or uses Redis/Postgres) and lists waiting requests from a store of thread ids.")


if __name__ == "__main__":
    main()
