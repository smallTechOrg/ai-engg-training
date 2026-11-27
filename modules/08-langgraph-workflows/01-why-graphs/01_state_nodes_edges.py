"""08.1/1  State, nodes and edges (no model yet)

The three parts of every LangGraph program, with no model involved so nothing distracts
from the structure:

  - the STATE: a TypedDict, the one shared record every step reads and writes;
  - NODES: plain Python functions that take the state and return the fields they changed;
  - EDGES: which node runs after which, from START to END.

You compile the graph, run it with invoke(), then watch it step by step with stream().

Run it:   ./run 08.1/1          (Windows: run 08.1/1)
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from labkit import lesson

TICKET = "  Ticket #5102: my MONITOR flickers and then goes black, about every ten minutes.  "


class TicketState(TypedDict, total=False):
    """Everything the workflow knows. Each node fills in more of it."""

    raw: str  # the ticket as it arrived
    text: str  # cleaned up by `clean`
    words: int  # counted by `clean`
    tags: list[str]  # added by `tag`


def clean(state: TicketState) -> dict:
    """Node 1: tidy the text. Returns only the fields it changes; LangGraph merges them in."""
    text = " ".join(state["raw"].split()).lower()
    return {"text": text, "words": len(text.split())}


KEYWORDS = {
    "hardware": ["monitor", "screen", "laptop", "keyboard", "printer"],
    "network": ["wi-fi", "wifi", "vpn", "internet"],
    "access": ["password", "locked", "mfa", "login"],
}


def tag(state: TicketState) -> dict:
    """Node 2: add tags by keyword. It can rely on `clean` having run first."""
    tags = [name for name, words in KEYWORDS.items() if any(word in state["text"] for word in words)]
    return {"tags": tags or ["other"]}


@lesson("08.1/1", "State, nodes and edges (no model yet)")
def main(ctx):
    ctx.step("Declare the graph: state, nodes, edges")
    ctx.note("StateGraph(TicketState) says what the shared state looks like.")
    ctx.note("add_node registers a function; add_edge says what runs next. START and END are built in.")
    builder = StateGraph(TicketState)
    builder.add_node("clean", clean)
    builder.add_node("tag", tag)
    builder.add_edge(START, "clean")
    builder.add_edge("clean", "tag")
    builder.add_edge("tag", END)

    ctx.step("Compile it")
    ctx.note("compile() checks the wiring (no orphan nodes, every edge points somewhere) and returns a runnable app.")
    graph = builder.compile()
    ctx.note(f"Nodes in the compiled graph: {', '.join(graph.get_graph().nodes)}")

    ctx.step("Run it once with invoke()")
    ctx.show_data("Input state", {"raw": TICKET})
    final = graph.invoke({"raw": TICKET})
    ctx.show_data("Final state (every field any node wrote)", final)

    ctx.step('Run it again with stream(stream_mode="updates")')
    ctx.note("Each item is {node name: the fields that node returned}. This is how you watch a workflow run.")
    for update in graph.stream({"raw": TICKET}, stream_mode="updates"):
        for node, changes in update.items():
            ctx.show_data(f"after node '{node}'", changes)

    ctx.step("Draw it")
    ctx.note("get_graph().draw_mermaid() returns Mermaid text. Paste it into any Mermaid viewer (or a README).")
    ctx.console.print(graph.get_graph().draw_mermaid(), markup=False, highlight=False)

    ctx.step("What you just saw")
    ctx.note("Two functions called one after the other: in plain Python that is tag(clean(ticket)).")
    ctx.note("The graph adds a named, shared state, a step-by-step trace, and a structure that can branch and loop.")
    ctx.note("No model was called. LangGraph is a workflow engine; models are just what some nodes do.")


if __name__ == "__main__":
    main()
