"""09.4/3  A sub-graph: a reusable drafter inside a bigger graph

A compiled graph is itself a node-shaped thing. Here a small graph (draft, check, revise
with a cap, like 09.1) is packaged once and used inside a parent graph that first picks a
tone from the ticket. Two ways to attach it:
  a. the sub-graph shares state keys with the parent: add it directly with add_node;
  b. the sub-graph has its own private state: wrap it in a function that maps keys in and out.
`stream(..., subgraphs=True)` shows which events came from inside the sub-graph.

Run it:   ./run 09.4/3          (Windows: run 09.4/3)
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from labkit import lesson

MAX_REVISIONS = 1
WORD_LIMIT = 40


# ---- the sub-graph: private state, its own loop -------------------------------------
class DrafterState(TypedDict):
    brief: str
    draft: str
    problems: list[str]
    revisions: int


# ---- the parent graph ---------------------------------------------------------------
class ParentState(TypedDict):
    ticket: str
    tone: str
    reply: str


@lesson("09.4/3", "A sub-graph as a node")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0.3)

    def write(state: DrafterState) -> dict:
        prompt = state["brief"]
        if state["problems"]:
            prompt += f"\n\nPrevious draft: {state['draft']}\nFix: {'; '.join(state['problems'])}"
        ai = model.invoke([("system", "Write a short IT helpdesk reply."), ("user", prompt)])
        ctx.record_usage(ai.usage_metadata)
        return {"draft": str(ai.content), "revisions": state["revisions"] + (1 if state["draft"] else 0)}

    def check(state: DrafterState) -> dict:
        words = len(state["draft"].split())
        return {"problems": [f"{words} words, limit {WORD_LIMIT}"] if words > WORD_LIMIT else []}

    def again(state: DrafterState) -> str:
        return END if not state["problems"] or state["revisions"] >= MAX_REVISIONS else "write"

    sg = StateGraph(DrafterState)
    sg.add_node("write", write)
    sg.add_node("check", check)
    sg.add_edge(START, "write")
    sg.add_edge("write", "check")
    sg.add_conditional_edges("check", again, ["write", END])
    drafter = sg.compile()
    ctx.step("The sub-graph on its own")
    ctx.note("nodes: " + ", ".join(n for n in drafter.get_graph().nodes if not n.startswith("__")))

    # Attach (b): private state, so wrap it and map keys in and out.
    def drafting_node(state: ParentState) -> dict:
        sub_out = drafter.invoke({"brief": f"Tone: {state['tone']}. Ticket: {state['ticket']}", "draft": "", "problems": [], "revisions": 0})
        return {"reply": sub_out["draft"]}

    def pick_tone(state: ParentState) -> dict:
        urgent = any(w in state["ticket"].lower() for w in ("down", "cannot", "urgent", "locked"))
        return {"tone": "calm and quick, acknowledge urgency" if urgent else "friendly and relaxed"}

    ctx.step("The parent graph: pick_tone -> drafting (the sub-graph) -> END")
    g = StateGraph(ParentState)
    g.add_node("pick_tone", pick_tone)
    g.add_node("drafting", drafting_node)
    g.add_edge(START, "pick_tone")
    g.add_edge("pick_tone", "drafting")
    g.add_edge("drafting", END)
    parent = g.compile()

    ctx.step("Run it")
    out = parent.invoke({"ticket": "I am locked out of my account before a customer demo (LL-3110).", "tone": "", "reply": ""})
    ctx.show_data("parent state", out)

    ctx.step("Attach (a) with shared keys, and stream to see the sub-graph's own events")

    class Shared(TypedDict):
        brief: str
        draft: str
        problems: list[str]
        revisions: int

    p2 = StateGraph(Shared)
    p2.add_node("drafter", drafter)  # compiled graph added directly: keys match, so no wrapper needed
    p2.add_edge(START, "drafter")
    p2.add_edge("drafter", END)
    outer = p2.compile()
    for namespace, update in outer.stream(
        {"brief": "Tell the employee their printer queue was cleared (ticket LL-3111).", "draft": "", "problems": [], "revisions": 0},
        stream_mode="updates", subgraphs=True,
    ):
        where = "parent" if not namespace else "inside " + namespace[0].split(":")[0]
        for node, delta in update.items():
            ctx.note(f"[{where}] node '{node}' wrote keys {sorted(delta)}")

    ctx.note("Sub-graphs let one team own 'how we draft replies' and many graphs reuse it.")


if __name__ == "__main__":
    main()
