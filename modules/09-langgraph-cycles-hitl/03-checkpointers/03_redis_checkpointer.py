"""09.3/3  A Redis checkpointer (needs a Redis server)

SQLite is one file on one machine. When several workers or a restarted container must
see the same threads, the checkpoints live in a server instead. This script keeps the
exact graph of 09.3/1 and only swaps the saver for `RedisSaver`. It needs `REDIS_URL`
in `.env` (and the `langgraph-checkpoint-redis` package). Without them it stops with a
clear message (exit code 3) and does not pretend to run.

Start Redis:   docker run --rm -p 6379:6379 redis/redis-stack-server:latest
               (RedisSaver needs the RediSearch and RedisJSON modules, which the
               plain `redis` image does not include)
Run it:   ./run 09.3/3          (Windows: run 09.3/3)
"""

import uuid
from typing import TypedDict

from labkit import lesson
from labkit.errors import ServiceUnavailable
from labkit.services import require


class State(TypedDict):
    ticket: str
    log: list[str]


@lesson("09.3/3", "Redis checkpointer")
def main(ctx):
    ctx.step("Check that Redis is configured and reachable")
    url = require("REDIS_URL")  # raises ServiceUnavailable (exit 3) with the start command when missing

    try:
        from langgraph.checkpoint.redis import RedisSaver
    except ImportError as exc:
        raise ServiceUnavailable(
            "The Redis checkpointer package is not installed",
            ["Install it:  uv sync --extra langgraph", f"(import failed: {exc})"],
        )

    from langgraph.graph import END, START, StateGraph

    def collect(state: State) -> dict:
        return {"log": state["log"] + ["collect"]}

    def provision(state: State) -> dict:
        return {"log": state["log"] + ["provision"]}

    g = StateGraph(State)
    g.add_node("collect", collect)
    g.add_node("provision", provision)
    g.add_edge(START, "collect")
    g.add_edge("collect", "provision")
    g.add_edge("provision", END)

    config = {"configurable": {"thread_id": f"lesson-09-3-{uuid.uuid4().hex[:8]}"}}

    ctx.step("Run with a RedisSaver")
    with RedisSaver.from_conn_string(url) as saver:
        saver.setup()  # creates the indexes once
        graph = g.compile(checkpointer=saver)
        final = graph.invoke({"ticket": "LL-2090", "log": []}, config)
        ctx.show_data("final state", final)

    ctx.step("Open a second connection: the thread is still there")
    with RedisSaver.from_conn_string(url) as saver:
        graph = g.compile(checkpointer=saver)
        ctx.show_data("state read back from Redis", graph.get_state(config).values)
        ctx.note(f"checkpoints for this thread: {len(list(graph.get_state_history(config)))}")

    ctx.note("Cleanup: the keys are named after this run's random thread_id; they expire or can be flushed in a dev Redis.")


if __name__ == "__main__":
    main()
