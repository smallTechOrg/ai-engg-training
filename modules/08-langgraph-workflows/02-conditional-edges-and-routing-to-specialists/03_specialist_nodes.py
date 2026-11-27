"""08.2/3  Scenario: route to specialist nodes with Command

Each specialist is a node with its own system prompt (a hardware engineer, an identity admin,
a network engineer, a general desk). New here: the classify node ROUTES ITSELF by returning
`Command(update=..., goto=...)`: one object that both writes state and names the next node.
That removes the separate router function, at the cost of the drawing not knowing the
branches unless you annotate the return type with `Literal[...]`.

Run it:   ./run 08.2/3          (Windows: run 08.2/3)
"""

from typing import Literal, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from labkit import lesson

TICKET = (
    "Ticket #5231 from Marta (Sales): since this morning my laptop will not join the office Wi-Fi, "
    "but my phone does. I have a customer demo at noon."
)

SPECIALISTS = {
    "hardware": "You are a Larkspur Labs hardware engineer. Give the single most useful physical or device check.",
    "access": "You are a Larkspur Labs identity admin. Give the account or MFA step that unblocks the user.",
    "network": "You are a Larkspur Labs network engineer. Give the most likely cause and the first thing to try.",
    "other": "You are a Larkspur Labs general helpdesk agent. Answer briefly or say who to ask.",
}


class State(TypedDict, total=False):
    ticket: str
    label: str
    answer: str
    specialist: str


@lesson("08.2/3", "Scenario: route to specialist nodes with Command")
def main(ctx):
    llm = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    def classify(state: State) -> Command[Literal["hardware", "access", "network", "other"]]:
        reply = llm.invoke(
            [
                ("system", "Classify the IT ticket. Answer with exactly one word: hardware, access, network or other."),
                ("human", state["ticket"]),
            ]
        )
        ctx.record_usage(reply.usage_metadata)
        raw = str(reply.content).lower()
        label = next((name for name in SPECIALISTS if name in raw.replace(".", " ").split()), "other")
        return Command(update={"label": label}, goto=label)  # write state AND choose the next node

    def make_specialist(name: str):
        def specialist(state: State) -> dict:
            reply = llm.invoke(
                [("system", SPECIALISTS[name] + " At most two sentences."), ("human", state["ticket"])]
            )
            ctx.record_usage(reply.usage_metadata)
            return {"answer": str(reply.content).strip(), "specialist": name}

        return specialist

    ctx.step("Build: classify returns a Command; specialists are plain nodes")
    builder = StateGraph(State)
    builder.add_node("classify", classify)
    for name in SPECIALISTS:
        builder.add_node(name, make_specialist(name))
        builder.add_edge(name, END)
    builder.add_edge(START, "classify")
    graph = builder.compile()
    ctx.note("There is no add_conditional_edges call: the Literal[...] return type tells LangGraph the possible targets.")
    ctx.console.print(graph.get_graph().draw_mermaid(), markup=False, highlight=False)

    ctx.step("Run the ticket and watch the route")
    ctx.show_data("Ticket", {"ticket": TICKET})
    for update in graph.stream({"ticket": TICKET}, stream_mode="updates"):
        for node, changes in update.items():
            ctx.show_data(f"after '{node}'", changes)
            if "answer" in changes:
                ctx.note(f"Answered by the {changes['specialist']} specialist:\n{changes['answer']}")

    ctx.step("Router function or Command?")
    ctx.note("add_conditional_edges: routing is separate from the node, easy to test, drawn from the path map.")
    ctx.note("Command(goto=...): one node decides and writes together; good when the choice needs the node's own work.")


if __name__ == "__main__":
    main()
