"""09.1/1  A cycle with a conditional edge (no model)

A LangGraph graph can loop. A conditional edge looks at the state and picks where to go next:
back to a node, or on to END. Here a node adds 1 to a counter until it reaches 3. Then the
same loop runs with a stop condition that never comes true, so you can see `recursion_limit`
stop it.

Run it:   ./run 09.1/1          (Windows: run 09.1/1)
"""

from typing import TypedDict

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph

from labkit import lesson


class State(TypedDict):
    count: int
    target: int


def bump(state: State) -> dict:
    return {"count": state["count"] + 1}


def should_continue(state: State) -> str:
    return "bump" if state["count"] < state["target"] else END


def build():
    g = StateGraph(State)
    g.add_node("bump", bump)
    g.add_edge(START, "bump")
    g.add_conditional_edges("bump", should_continue, ["bump", END])
    return g.compile()


@lesson("09.1/1", "A cycle with a conditional edge")
def main(ctx):
    graph = build()

    ctx.step("Run a loop that terminates")
    ctx.note("The rule: run bump again while count < target, otherwise go to END. State prints after each node.")
    for update in graph.stream({"count": 0, "target": 3}, stream_mode="values"):
        ctx.note(f"state = {update}")

    ctx.step("A loop whose stop condition is never met")
    ctx.note("target=100 cannot be reached in 5 steps (recursion_limit=5), so LangGraph raises GraphRecursionError.")
    try:
        graph.invoke({"count": 0, "target": 100}, config={"recursion_limit": 5})
    except GraphRecursionError as exc:
        ctx.note(f"GraphRecursionError: {str(exc).splitlines()[0][:120]}")

    ctx.step("Why this matters")
    ctx.note("The default limit is 25 steps. For any graph with a cycle, set it on purpose and keep your own counter in the state.")


if __name__ == "__main__":
    main()
