"""09.4/2  Parallel model workers: triage five tickets at once

This is the same Send pattern as 09.4/1, but each worker is a model call that classifies
one ticket. A reducer collects the answers, and a final node in plain Python counts them
per category. Five tickets means five model calls, all made at the same time. By hand
(module 02) this would be a loop of five `create()` calls, or `asyncio.gather` (module 05).

Run it:   ./run 09.4/2          (Windows: run 09.4/2)
"""

import operator
import time
from collections import Counter
from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from labkit import lesson

CATEGORIES = ["hardware", "network", "account", "software", "other"]
TICKETS = {
    "LL-3101": "My monitor flickers whenever I plug in the dock.",
    "LL-3102": "I cannot log in, it says my password expired and the reset email never arrives.",
    "LL-3103": "Wifi on the 3rd floor drops every few minutes.",
    "LL-3104": "Please install the latest PDF editor on my laptop.",
    "LL-3105": "Where do I find the office plant watering rota?",
}


class State(TypedDict):
    tickets: dict[str, str]
    labels: Annotated[list[dict], operator.add]
    summary: dict[str, int]


class Job(TypedDict):
    ticket_id: str
    text: str


def normalise(raw: str) -> str:
    """Map whatever the model said onto one of our categories, or 'other'."""
    text = raw.strip().lower()
    for cat in CATEGORIES:
        if cat in text:
            return cat
    return "other"


@lesson("09.4/2", "Parallel ticket triage")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    def fan_out(state: State) -> list[Send]:
        return [Send("classify", {"ticket_id": k, "text": v}) for k, v in state["tickets"].items()]

    def classify(job: Job) -> dict:
        ai = model.invoke([
            ("system", f"Classify the helpdesk ticket. Answer with exactly one word from: {', '.join(CATEGORIES)}."),
            ("user", job["text"]),
        ])
        ctx.record_usage(ai.usage_metadata)
        label = normalise(str(ai.content))
        ctx.note(f"[worker] {job['ticket_id']} -> {label} (model said: {str(ai.content).strip()[:30]!r})")
        return {"labels": [{"ticket_id": job["ticket_id"], "label": label}]}

    def summarise(state: State) -> dict:
        return {"summary": dict(Counter(item["label"] for item in state["labels"]))}

    ctx.step("Build: START -> Send(classify) x N -> summarise")
    g = StateGraph(State)
    g.add_node("classify", classify)
    g.add_node("summarise", summarise)
    g.add_conditional_edges(START, fan_out, ["classify"])
    g.add_edge("classify", "summarise")
    g.add_edge("summarise", END)
    graph = g.compile()

    ctx.step("Run")
    start = time.perf_counter()
    out = graph.invoke({"tickets": TICKETS, "labels": [], "summary": {}})
    ctx.note(f"wall time for {len(TICKETS)} model calls: {time.perf_counter() - start:.1f}s (they overlap)")

    ctx.step("Result")
    ctx.show_data("labels sorted by ticket id", sorted(out["labels"], key=lambda x: x["ticket_id"]))
    ctx.show_data("summary", out["summary"])
    ctx.note("The workers can finish in any order. Sort by an id when the order matters.")


if __name__ == "__main__":
    main()
