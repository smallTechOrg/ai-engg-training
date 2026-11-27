"""08.4/1  Build the helpdesk router

The graph for the capstone: classify -> (conditional edge) -> one of five specialists ->
finalise. Specialists are model nodes with their own system prompts; `finalise` is a plain
node that adds the sign-off and a priority. The classifier output is normalised so a messy
answer lands in `other`. One ticket runs through it with updates streaming.

Run it:   ./run 08.4/1          (Windows: run 08.4/1)
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from labkit import lesson

LABELS = ("hardware", "access", "network", "software", "other")

SPECIALISTS = {
    "hardware": "You are a Larkspur Labs hardware engineer. Give the safest first step and say if a visit is needed.",
    "access": "You are a Larkspur Labs identity admin. Give the account or MFA step that unblocks the user.",
    "network": "You are a Larkspur Labs network engineer. Give the likely cause and the first thing to try.",
    "software": "You are a Larkspur Labs software desk agent. Say how the install or fix is requested and approved.",
    "other": "You are a Larkspur Labs general helpdesk agent. Answer briefly or say who to ask.",
}

TICKET = "Ticket #5410 from Dev (Platform): MFA codes from my new phone are rejected and I have a deploy in an hour."


class State(TypedDict, total=False):
    ticket: str
    label: str
    answer: str
    reply: str


def normalise(raw: str) -> str:
    words = raw.lower().replace(".", " ").replace(",", " ").split()
    return next((w for w in words if w in LABELS), "other")


def build_graph(classify_llm, draft_llm):
    """Both models are arguments so tests (08.4/3) can pass fakes."""

    def classify(state: State) -> dict:
        reply = classify_llm.invoke(
            [("system", "Classify the IT ticket. One word: hardware, access, network, software or other."), ("human", state["ticket"])]
        )
        return {"label": normalise(str(reply.content))}

    def make_specialist(name: str):
        def specialist(state: State) -> dict:
            reply = draft_llm.invoke([("system", SPECIALISTS[name] + " At most two sentences."), ("human", state["ticket"])])
            return {"answer": str(reply.content).strip()}

        return specialist

    def finalise(state: State) -> dict:
        body = state.get("answer") or "(no answer was produced; a person will follow up)"
        return {"reply": f"{body}\n\nLarkspur IT (handled by: {state['label']})"}

    builder = StateGraph(State)
    builder.add_node("classify", classify)
    builder.add_node("finalise", finalise)
    for name in LABELS:
        builder.add_node(name, make_specialist(name))
        builder.add_edge(name, "finalise")
    builder.add_edge(START, "classify")
    builder.add_conditional_edges("classify", lambda s: s["label"], {n: n for n in LABELS})
    builder.add_edge("finalise", END)
    return builder.compile()


class Counted:
    """Wraps a ChatOpenAI so every call's tokens are recorded."""

    def __init__(self, llm, ctx):
        self.llm, self.ctx = llm, ctx

    def invoke(self, messages):
        reply = self.llm.invoke(messages)
        self.ctx.record_usage(reply.usage_metadata)
        return reply


@lesson("08.4/1", "Build the helpdesk router")
def main(ctx):
    llm = Counted(
        ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0), ctx
    )
    ctx.step("Build the graph")
    graph = build_graph(llm, llm)
    ctx.console.print(graph.get_graph().draw_mermaid(), markup=False, highlight=False)

    ctx.step("Run one ticket and watch each node")
    ctx.show_data("Input", {"ticket": TICKET})
    final = {}
    for update in graph.stream({"ticket": TICKET}, stream_mode="updates"):
        for node, changes in update.items():
            final.update(changes)
            ctx.show_data(f"after '{node}'", changes)

    ctx.step("The reply a person would receive")
    ctx.note(final.get("reply", "(none)"))
    ctx.note("Four nodes ran: classify, one specialist, finalise. The other four specialists never did.")


if __name__ == "__main__":
    main()
