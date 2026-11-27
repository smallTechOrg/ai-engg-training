"""08.2/2  A model as the router, with a safe fallback

Keywords break on "my screen keeps freezing when I open the VPN client". A model can read the
ticket and pick the branch. The idea is still the same conditional edge, but the dangerous
part is new: a model's answer is free text, so the router MUST map it onto the known branch
names and fall back to a default when the answer is not one of them.

Run it:   ./run 08.2/2          (Windows: run 08.2/2)
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from labkit import lesson

LABELS = ("hardware", "access", "network", "other")

TICKETS = [
    "Ticket #5211: the screen on my docking station keeps freezing for a second, then recovers.",
    "Ticket #5212: MFA codes from my phone are rejected, and I have a deploy in an hour.",
    "Ticket #5213: when is the office closed for the winter holidays?",
]


class State(TypedDict, total=False):
    ticket: str
    raw_label: str  # exactly what the model said
    label: str  # the cleaned label the router uses
    handled_by: str


def normalise(raw: str) -> str:
    """Map free text onto a known label, or 'other'. This is the guard rail of the whole lesson."""
    words = raw.lower().replace(".", " ").replace(",", " ").replace(":", " ").split()
    for word in words:
        if word in LABELS:
            return word
    return "other"


@lesson("08.2/2", "A model as the router, with a safe fallback")
def main(ctx):
    llm = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    def classify(state: State) -> dict:
        # A normal node: it WRITES the label into the state. Routing happens after it.
        reply = llm.invoke(
            [
                ("system", "Classify the IT ticket. Answer with exactly one word: hardware, access, network or other."),
                ("human", state["ticket"]),
            ]
        )
        ctx.record_usage(reply.usage_metadata)
        raw = str(reply.content).strip()
        return {"raw_label": raw, "label": normalise(raw)}

    def pick(state: State) -> str:
        # The router: pure function of the state, returns a node name.
        return state["label"]

    def make_node(name: str):
        return lambda state: {"handled_by": name}

    ctx.step("Build: classify (model) -> conditional edge -> one node per label")
    builder = StateGraph(State)
    builder.add_node("classify", classify)
    for name in LABELS:
        builder.add_node(name, make_node(name))
        builder.add_edge(name, END)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges("classify", pick, {name: name for name in LABELS})
    graph = builder.compile()
    ctx.console.print(graph.get_graph().draw_mermaid(), markup=False, highlight=False)
    ctx.note("Splitting 'classify' (writes state) from 'pick' (reads state) keeps the decision visible in the state.")

    ctx.step("Run three tickets")
    for ticket in TICKETS:
        result = graph.invoke({"ticket": ticket})
        ctx.show_data(
            ticket[:22],
            {"model said": result["raw_label"], "routed to": result["handled_by"]},
        )

    ctx.step("Why normalise?")
    ctx.note("If the router returned a name that is not in the path map, LangGraph raises an error mid-run.")
    for raw in ("Hardware.", "I think this is a network problem", "banana"):
        ctx.note(f"normalise({raw!r}) -> {normalise(raw)!r}")
    ctx.note("Models answer in sentences, with capitals and full stops, or off-script. Always map to a known set.")


if __name__ == "__main__":
    main()
