"""09.2/3  Approve, edit or reject, then do the risky thing

The reviewer now has three choices instead of two: they can also EDIT the proposed action
before it runs. The model proposes an action for a helpdesk request, and the graph pauses
BEFORE the side effect. Only an approved (or edited) action is carried out. The side effect
here just adds a line to a fake audit list. Nothing real happens.

Run it:   ./run 09.2/3          (Windows: run 09.2/3)
"""

import operator
from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from labkit import lesson

REQUESTS = {
    "LL-2071": "Please unlock my account, I typed the password wrong five times.",
    "LL-2072": "I need admin rights on the build server for a one-off migration.",
    "LL-2073": "Delete all mailboxes of people who left last year.",
}
# The scripted reviewer: one decision per ticket.
DECISIONS = {
    "LL-2071": {"action": "approve"},
    "LL-2072": {"action": "edit", "proposal": "Grant temporary admin on the build server for 24 hours, then revoke."},
    "LL-2073": {"action": "reject", "reason": "Needs a records-retention review first."},
}


class State(TypedDict):
    ticket_id: str
    request: str
    proposal: str
    audit: Annotated[list[str], operator.add]


@lesson("09.2/3", "Approve, edit or reject")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    def propose(state: State) -> dict:
        ai = model.invoke([
            ("system", "You are an IT helpdesk agent. Propose ONE concrete action in one sentence. No preamble."),
            ("user", state["request"]),
        ])
        ctx.record_usage(ai.usage_metadata)
        return {"proposal": str(ai.content).strip()}

    def approval_gate(state: State) -> Command:
        decision = interrupt({"ticket": state["ticket_id"], "proposal": state["proposal"], "options": ["approve", "edit", "reject"]})
        action = decision.get("action")
        if action == "approve":
            return Command(goto="execute")
        if action == "edit":
            return Command(goto="execute", update={"proposal": decision["proposal"], "audit": ["edited by reviewer"]})
        return Command(goto=END, update={"audit": [f"rejected: {decision.get('reason', 'no reason given')}"]})

    def execute(state: State) -> dict:
        # The only node with a side effect. It is only reachable through the gate.
        return {"audit": [f"EXECUTED: {state['proposal']}"]}

    g = StateGraph(State)
    g.add_node("propose", propose)
    g.add_node("approval_gate", approval_gate, destinations=("execute", END))
    g.add_node("execute", execute)
    g.add_edge(START, "propose")
    g.add_edge("propose", "approval_gate")
    g.add_edge("execute", END)
    graph = g.compile(checkpointer=InMemorySaver())

    ctx.step("Three tickets, three threads, three decisions")
    for tid, text in REQUESTS.items():
        config = {"configurable": {"thread_id": tid}}
        result = graph.invoke({"ticket_id": tid, "request": text, "proposal": "", "audit": []}, config)
        if "__interrupt__" in result:
            payload = result["__interrupt__"][0].value
            ctx.note(f"[{tid}] paused. proposal: {payload['proposal'][:110]}")
            ctx.note(f"[{tid}] reviewer decides: {DECISIONS[tid]}")
            result = graph.invoke(Command(resume=DECISIONS[tid]), config)
        ctx.note(f"[{tid}] audit trail: {result['audit']}")

    ctx.step("What the pattern guarantees")
    ctx.note("'execute' is only reachable from the gate, and the gate only proceeds on approve or edit.")
    ctx.note("A model cannot talk its way past the gate. The check is built into the graph, not written in a prompt.")


if __name__ == "__main__":
    main()
