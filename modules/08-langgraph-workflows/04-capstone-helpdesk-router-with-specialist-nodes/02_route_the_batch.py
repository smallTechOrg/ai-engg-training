"""08.4/2  Route the batch and measure the router

Run every ticket in tickets.json through the graph and compare the label the router chose
with the expected one. To stay inside a small call budget the specialists are canned here
(no model); only the classifier uses the model, one call per ticket. Acceptance bar: at least
6 of 8 routed correctly.

Run it:   ./run 08.4/2          (Windows: run 08.4/2)
"""

import json
from pathlib import Path
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from labkit import lesson

LABELS = ("hardware", "access", "network", "software", "other")
BAR = 6
TICKETS = json.loads((Path(__file__).parent / "tickets.json").read_text(encoding="utf-8"))


class State(TypedDict, total=False):
    ticket: str
    label: str
    answer: str


def normalise(raw: str) -> str:
    words = raw.lower().replace(".", " ").replace(",", " ").split()
    return next((w for w in words if w in LABELS), "other")


@lesson("08.4/2", "Route the batch and measure the router")
def main(ctx):
    llm = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    def classify(state: State) -> dict:
        reply = llm.invoke(
            [("system", "Classify the IT ticket. One word: hardware, access, network, software or other."), ("human", state["ticket"])]
        )
        ctx.record_usage(reply.usage_metadata)
        return {"label": normalise(str(reply.content))}

    builder = StateGraph(State)
    builder.add_node("classify", classify)
    for name in LABELS:
        builder.add_node(name, lambda state, n=name: {"answer": f"[canned {n} playbook]"})
        builder.add_edge(name, END)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges("classify", lambda s: s["label"], {n: n for n in LABELS})
    graph = builder.compile()

    ctx.step("Route all tickets")
    rows = []
    for ticket in TICKETS:
        result = graph.invoke({"ticket": ticket["text"]})
        rows.append({"id": ticket["id"], "expected": ticket["expected"], "routed": result["label"]})
        mark = "ok  " if result["label"] == ticket["expected"] else "MISS"
        ctx.note(f"{mark} #{ticket['id']}: expected {ticket['expected']:<9} routed {result['label']}")

    ctx.step("Score")
    correct = sum(r["expected"] == r["routed"] for r in rows)
    ctx.note(f"{correct} of {len(rows)} routed correctly (bar: {BAR}).")
    ctx.note("PASS" if correct >= BAR else "FAIL: below the acceptance bar. Read the misses and tighten the classifier prompt.")
    confusion = {}
    for r in rows:
        if r["expected"] != r["routed"]:
            confusion[f"{r['expected']} -> {r['routed']}"] = confusion.get(f"{r['expected']} -> {r['routed']}", 0) + 1
    ctx.show_data("Misroutes", confusion or "none")


if __name__ == "__main__":
    main()
