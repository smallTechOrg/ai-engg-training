"""08.4/3  Test the whole router offline

The capstone's safety net: checks that run with fake models, no network and no cost.
It covers the router decision for each label, the fallback for a messy answer, the shape of
the final reply, and that exactly one specialist runs. It also writes the graph's Mermaid
to a temp folder. Fails loudly (a FAIL line, never a crash) if any check breaks.

Run it:   ./run 08.4/3          (Windows: run 08.4/3)
"""

import tempfile
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from labkit import lesson

LABELS = ("hardware", "access", "network", "software", "other")


class State(TypedDict, total=False):
    ticket: str
    label: str
    answer: str
    reply: str


class Fake:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return type("R", (), {"content": self.text, "usage_metadata": None})()


def normalise(raw: str) -> str:
    words = raw.lower().replace(".", " ").replace(",", " ").split()
    return next((w for w in words if w in LABELS), "other")


def build_graph(classify_llm, draft_llm):
    def classify(state: State) -> dict:
        return {"label": normalise(str(classify_llm.invoke([("human", state["ticket"])]).content))}

    def make_specialist(name):
        return lambda state: {"answer": str(draft_llm.invoke([("human", state["ticket"])]).content)}

    def finalise(state: State) -> dict:
        return {"reply": f"{state.get('answer') or '(no answer)'}\n\nLarkspur IT (handled by: {state['label']})"}

    builder = StateGraph(State)
    builder.add_node("classify", classify)
    builder.add_node("finalise", finalise)
    for name in LABELS:
        builder.add_node(name, make_specialist(name))
        builder.add_edge(name, "finalise")
    builder.add_edge(START, "classify")
    builder.add_conditional_edges("classify", lambda s: s["label"], {n: n for n in LABELS})
    builder.add_edge("finalise", END)
    return builder.compile()


@lesson("08.4/3", "Test the whole router offline")
def main(ctx):
    results = []

    def check(name, ok):
        results.append(bool(ok))
        ctx.note(f"{'PASS' if ok else 'FAIL'}  {name}")

    ctx.step("Every label reaches its own specialist")
    for label in LABELS:
        graph = build_graph(Fake(label), Fake(f"answer from {label}"))
        out = graph.invoke({"ticket": "t"})
        check(f"classifier says {label!r} -> reply mentions 'handled by: {label}'", f"handled by: {label}" in out["reply"])

    ctx.step("Messy classifier answers fall back to 'other'")
    for raw in ("Hardware.", "", "I would say it is a network problem", "unknown"):
        graph = build_graph(Fake(raw), Fake("a"))
        label = graph.invoke({"ticket": "t"})["label"]
        check(f"{raw!r} -> {label!r}", label == normalise(raw))
    check("empty and unknown answers give 'other'", normalise("") == "other" and normalise("unknown") == "other")

    ctx.step("Only one specialist runs, and the model is called twice")
    classifier, drafter = Fake("access"), Fake("Reset MFA.")
    visited = [n for u in build_graph(classifier, drafter).stream({"ticket": "t"}, stream_mode="updates") for n in u]
    check(f"visited {visited}", visited == ["classify", "access", "finalise"])
    check("classifier called once, drafter once", (classifier.calls, drafter.calls) == (1, 1))

    ctx.step("An empty draft still produces a usable reply")
    out = build_graph(Fake("network"), Fake("")).invoke({"ticket": "t"})
    check("reply says no answer was produced", "(no answer)" in out["reply"])

    ctx.step("Save the diagram")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "router.mmd"
        path.write_text(build_graph(Fake("x"), Fake("y")).get_graph().draw_mermaid(), encoding="utf-8")
        check(f"mermaid written ({path.stat().st_size} bytes)", path.stat().st_size > 100)

    ctx.step("Result")
    ctx.note(f"{sum(results)} of {len(results)} checks passed.")
    ctx.note("No model was called. Wire these checks into pytest as they are.")


if __name__ == "__main__":
    main()
