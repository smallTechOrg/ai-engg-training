"""09.3/1  A SQLite checkpointer and a simulated crash (no model)

A checkpointer saves the graph state after every step. Here the checkpoints go to a
SQLite file. Step 2 "crashes" on the first run; we then open the file again with a brand
new graph object (as a restarted process would) and continue from the saved step instead
of starting over. Steps that already finished do not run twice.

Run it:   ./run 09.3/1          (Windows: run 09.3/1)
"""

import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from labkit import lesson


class State(TypedDict):
    ticket: str
    log: list[str]


CRASH = {"armed": True}  # step 2 fails once while this is True


def build(saver):
    def collect(state: State) -> dict:
        return {"log": state["log"] + ["collect: read ticket"]}

    def provision(state: State) -> dict:
        if CRASH["armed"]:
            raise RuntimeError("worker killed while provisioning")
        return {"log": state["log"] + ["provision: account created"]}

    def notify(state: State) -> dict:
        return {"log": state["log"] + ["notify: employee emailed"]}

    g = StateGraph(State)
    g.add_node("collect", collect)
    g.add_node("provision", provision)
    g.add_node("notify", notify)
    g.add_edge(START, "collect")
    g.add_edge("collect", "provision")
    g.add_edge("provision", "notify")
    g.add_edge("notify", END)
    return g.compile(checkpointer=saver)


@lesson("09.3/1", "SQLite checkpointer and resume")
def main(ctx):
    config = {"configurable": {"thread_id": "onboarding-LL-2080"}}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = str(Path(tmp) / "checkpoints.sqlite")

        ctx.step("Process 1: run until the crash")
        with SqliteSaver.from_conn_string(db) as saver:
            graph = build(saver)
            try:
                graph.invoke({"ticket": "LL-2080 new hire", "log": []}, config)
            except RuntimeError as exc:
                ctx.note(f"crashed: {exc}")
            snap = graph.get_state(config)
            ctx.note(f"saved state: {snap.values}")
            ctx.note(f"next node to run: {snap.next}")
        ctx.note("The with-block closed the connection: that process is gone. Only the file remains.")
        ctx.note(f"checkpoint file exists: {Path(db).exists()} ({Path(db).stat().st_size} bytes)")

        ctx.step("Process 2: new connection, new graph object, same thread_id")
        CRASH["armed"] = False  # the bug is fixed / the worker is back
        with SqliteSaver.from_conn_string(db) as saver:
            graph = build(saver)
            ctx.note(f"state loaded from the file: {graph.get_state(config).values}")
            ctx.note("invoke(None, config) means: no new input, continue from the last checkpoint.")
            final = graph.invoke(None, config)
            ctx.show_data("final state", final)

            ctx.step("The checkpoint history")
            for snap in graph.get_state_history(config):
                ctx.note(f"step {snap.metadata.get('step')}: next={snap.next} log entries={len(snap.values.get('log', []))}")

    ctx.step("What to take away")
    ctx.note("'collect' ran once, not twice: the first run's result was loaded, not recomputed.")
    ctx.note("SqliteSaver is a good default for one machine: no server, one file. Use Redis or Postgres when several workers share state.")


if __name__ == "__main__":
    main()
