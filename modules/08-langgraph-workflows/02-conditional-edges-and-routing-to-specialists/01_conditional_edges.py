"""08.2/1  Conditional edges (no model)

An ordinary edge always goes to the same next node. A CONDITIONAL edge calls a small
"router" function with the state and uses what it returns to pick the next node. The router
only decides; it does not change the state. Here the router is plain keyword matching so
you can see the mechanism with nothing else going on.

Run it:   ./run 08.2/1          (Windows: run 08.2/1)
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from labkit import lesson

TICKETS = [
    "Ticket #5201: my monitor flickers and goes black every ten minutes.",
    "Ticket #5202: I am locked out after too many wrong passwords.",
    "Ticket #5203: can you recommend a good book about databases?",
]


class State(TypedDict, total=False):
    ticket: str
    handled_by: str
    plan: str


def route(state: State) -> str:
    """The router: returns the NAME of the next node. It must not return anything else."""
    text = state["ticket"].lower()
    if any(word in text for word in ("monitor", "laptop", "keyboard", "printer")):
        return "hardware"
    if any(word in text for word in ("password", "locked", "mfa")):
        return "access"
    return "fallback"


def hardware(state: State) -> dict:
    return {"handled_by": "hardware", "plan": "Check cables, swap the monitor, book a desk visit."}


def access(state: State) -> dict:
    return {"handled_by": "access", "plan": "Verify identity, unlock the account, resend the MFA enrolment link."}


def fallback(state: State) -> dict:
    return {"handled_by": "fallback", "plan": "Not an IT issue: reply politely and close."}


@lesson("08.2/1", "Conditional edges (no model)")
def main(ctx):
    ctx.step("Wire a graph with one conditional edge")
    ctx.note("add_conditional_edges(source, router) runs router(state) after `source` and goes to the node it names.")
    builder = StateGraph(State)
    builder.add_node("hardware", hardware)
    builder.add_node("access", access)
    builder.add_node("fallback", fallback)
    builder.add_conditional_edges(START, route)  # decide straight from the start
    for name in ("hardware", "access", "fallback"):
        builder.add_edge(name, END)
    graph = builder.compile()

    ctx.step("Without a path map the drawing cannot show the branches")
    ctx.console.print(graph.get_graph().draw_mermaid(), markup=False, highlight=False)
    ctx.note("LangGraph cannot read the possible return values out of a function: the drawing only shows START -> END and hides all three nodes.")

    ctx.step("Give the router a path map")
    ctx.note("A dict {return value: node} documents the choices, so the drawing shows real branches and labels.")
    builder = StateGraph(State)
    builder.add_node("hardware", hardware)
    builder.add_node("access", access)
    builder.add_node("fallback", fallback)
    builder.add_conditional_edges(
        START, route, {"hardware": "hardware", "access": "access", "fallback": "fallback"}
    )
    for name in ("hardware", "access", "fallback"):
        builder.add_edge(name, END)
    graph = builder.compile()
    ctx.console.print(graph.get_graph().draw_mermaid(), markup=False, highlight=False)

    ctx.step("Run three tickets and see which branch each takes")
    for ticket in TICKETS:
        result = graph.invoke({"ticket": ticket})
        ctx.show_data(ticket[:22], {"handled_by": result["handled_by"], "plan": result["plan"]})

    ctx.step("What you just saw")
    ctx.note("The router is an ordinary function, so you can unit test it (08.3) without running the graph.")
    ctx.note("Only one branch ran per ticket: the others were never called.")


if __name__ == "__main__":
    main()
