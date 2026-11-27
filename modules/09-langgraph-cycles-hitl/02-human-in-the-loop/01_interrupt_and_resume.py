"""09.2/1  interrupt() and Command(resume=...) (no model)

A node calls `interrupt(payload)`. The graph stops, saves its state in the checkpointer
and hands the payload back to the caller. Later the caller runs the graph again with
`Command(resume=value)` on the same thread. This time `interrupt()` returns `value` inside
the node and the run carries on. In between, a person decides (here, a script plays the person).

Run it:   ./run 09.2/1          (Windows: run 09.2/1)
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from labkit import lesson


class State(TypedDict):
    request: str
    decision: str
    result: str


def ask_manager(state: State) -> dict:
    # Everything BEFORE interrupt() runs again when the graph resumes, so keep this node small.
    answer = interrupt({"question": "Approve this request?", "request": state["request"]})
    return {"decision": str(answer)}


def act(state: State) -> dict:
    if state["decision"] == "yes":
        return {"result": f"done: {state['request']}"}
    return {"result": f"skipped: {state['request']}"}


def build():
    g = StateGraph(State)
    g.add_node("ask_manager", ask_manager)
    g.add_node("act", act)
    g.add_edge(START, "ask_manager")
    g.add_edge("ask_manager", "act")
    g.add_edge("act", END)
    # Interrupts need a checkpointer, because that is where the paused state is saved.
    return g.compile(checkpointer=InMemorySaver())


@lesson("09.2/1", "interrupt and resume")
def main(ctx):
    graph = build()
    config = {"configurable": {"thread_id": "ticket-LL-2050"}}

    ctx.step("Run until the interrupt")
    first = graph.invoke({"request": "Grant Priya access to the finance share", "decision": "", "result": ""}, config)
    ctx.show_data("invoke() returned", first)
    ctx.note("The result holds '__interrupt__' with the payload given to interrupt(). The graph is paused, not finished.")

    ctx.step("Look at the paused state")
    snap = graph.get_state(config)
    ctx.note(f"next node to run: {snap.next}")
    ctx.note(f"pending interrupt value: {snap.tasks[0].interrupts[0].value}")
    ctx.note(f"state values so far: {snap.values}")

    ctx.step("Resume with a decision")
    ctx.note("Command(resume='yes') on the same thread_id. interrupt() now returns 'yes'.")
    final = graph.invoke(Command(resume="yes"), config)
    ctx.show_data("final state", final)
    ctx.note(f"next after finishing: {graph.get_state(config).next} (empty means the run is complete)")

    ctx.step("A second thread is independent")
    other = {"configurable": {"thread_id": "ticket-LL-2051"}}
    graph.invoke({"request": "Reset the CEO's password", "decision": "", "result": ""}, other)
    final2 = graph.invoke(Command(resume="no"), other)
    ctx.note(f"thread LL-2051 -> {final2['result']}")
    ctx.note(f"thread LL-2050 still says: {graph.get_state(config).values['result']}")


if __name__ == "__main__":
    main()
