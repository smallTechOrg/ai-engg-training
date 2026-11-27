"""09.4/1  Fan out and fan in with Send (no model)

LangGraph has two ways to run work in parallel:
1. Static: one node has several outgoing edges, and all the targets run in the same step.
2. Dynamic (map-reduce): a conditional edge returns a list of `Send(node, payload)`, one per
   item, so the number of workers is decided while the graph runs. Each worker returns part
   of the result, and a REDUCER on the state key (here `operator.add`) merges the parts.

Run it:   ./run 09.4/1          (Windows: run 09.4/1)
"""

import operator
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from labkit import lesson

TICKETS = ["LL-3001 printer jam", "LL-3002 vpn drops", "LL-3003 new laptop", "LL-3004 wifi slow"]


class State(TypedDict):
    tickets: list[str]
    results: Annotated[list[str], operator.add]  # the reducer: lists from parallel workers are joined end to end


class WorkerInput(TypedDict):
    ticket: str


@lesson("09.4/1", "Fan out and fan in with Send")
def main(ctx):
    ctx.step("Static parallel branches")

    class S1(TypedDict):
        notes: Annotated[list[str], operator.add]

    g1 = StateGraph(S1)
    g1.add_node("check_vpn", lambda s: {"notes": ["vpn ok"]})
    g1.add_node("check_mail", lambda s: {"notes": ["mail ok"]})
    g1.add_node("join", lambda s: {"notes": [f"joined after {len(s['notes'])} checks"]})
    g1.add_edge(START, "check_vpn")
    g1.add_edge(START, "check_mail")
    g1.add_edge("check_vpn", "join")
    g1.add_edge("check_mail", "join")
    g1.add_edge("join", END)
    ctx.note(f"notes: {g1.compile().invoke({'notes': []})['notes']}")
    ctx.note("'join' waited for both branches because both point at it.")

    ctx.step("Dynamic fan-out: one worker per ticket, count decided at run time")

    def fan_out(state: State) -> list[Send]:
        ctx.note(f"[fan_out] {len(state['tickets'])} tickets -> {len(state['tickets'])} Send() objects")
        return [Send("worker", {"ticket": t}) for t in state["tickets"]]

    def worker(payload: WorkerInput) -> dict:
        time.sleep(0.2)  # pretend to do slow work; the workers run at the same time
        return {"results": [f"{payload['ticket'].split()[0]}: handled"]}

    def collect(state: State) -> dict:
        ctx.note(f"[collect] got {len(state['results'])} results")
        return {}

    g = StateGraph(State)
    g.add_node("worker", worker)
    g.add_node("collect", collect)
    g.add_conditional_edges(START, fan_out, ["worker"])
    g.add_edge("worker", "collect")
    g.add_edge("collect", END)
    graph = g.compile()

    start = time.perf_counter()
    out = graph.invoke({"tickets": TICKETS, "results": []})
    elapsed = time.perf_counter() - start
    ctx.show_data("results (order is the order of the Send list)", out["results"])
    ctx.note(f"4 workers of 0.2s each took {elapsed:.2f}s: they ran in parallel (sequential would be 0.8s).")

    ctx.step("Zero items")
    ctx.note(f"no tickets -> results = {graph.invoke({'tickets': [], 'results': []})['results']}")
    ctx.note("Watch out: with an empty Send list no worker runs, so 'collect' never runs either.")

    ctx.step("Why the reducer matters")
    ctx.note("Without Annotated[..., operator.add], four workers writing 'results' in one step raise InvalidUpdateError.")


if __name__ == "__main__":
    main()
