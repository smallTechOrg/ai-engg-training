"""08.3/3  Scenario: test the router without a model

A graph is just functions, so most of it can be tested without calling a model:
  1. test a NODE by calling it as a plain function with a small state dict;
  2. test the ROUTER the same way;
  3. test the whole GRAPH by swapping the model for a fake with the same interface,
     so the test is fast, free and always gives the same answer.
Then the same graph runs once against the real model, to compare.

The checks use plain `assert` inside a tiny runner so you see each result.

Run it:   ./run 08.3/3          (Windows: run 08.3/3)
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from labkit import lesson

LABELS = ("hardware", "access", "network", "other")


class State(TypedDict, total=False):
    ticket: str
    label: str
    handled_by: str


def normalise(raw: str) -> str:
    words = raw.lower().replace(".", " ").replace(",", " ").split()
    return next((w for w in words if w in LABELS), "other")


def route(state: State) -> str:
    return state["label"]


class FakeModel:
    """Same .invoke() shape as ChatOpenAI for our use: returns an object with .content and .usage_metadata."""

    def __init__(self, answer: str):
        self.answer = answer

    def invoke(self, messages):
        return type("FakeReply", (), {"content": self.answer, "usage_metadata": None})()


def build_graph(llm):
    """Dependency injection: the graph takes the model as an argument, so tests can pass a fake."""

    def classify(state: State) -> dict:
        reply = llm.invoke([("system", "One word: hardware, access, network or other."), ("human", state["ticket"])])
        return {"label": normalise(str(reply.content))}

    builder = StateGraph(State)
    builder.add_node("classify", classify)
    for name in LABELS:
        builder.add_node(name, lambda state, n=name: {"handled_by": n})
        builder.add_edge(name, END)
    builder.add_edge(START, "classify")
    builder.add_conditional_edges("classify", route, {n: n for n in LABELS})
    return builder.compile()


@lesson("08.3/3", "Scenario: test the router without a model")
def main(ctx):
    results = []

    def check(name, condition):
        results.append(bool(condition))
        ctx.note(f"{'PASS' if condition else 'FAIL'}  {name}")

    ctx.step("1. Test the helper and the router as plain functions")
    check("normalise('Hardware.') == 'hardware'", normalise("Hardware.") == "hardware")
    check("normalise('banana') == 'other'", normalise("banana") == "other")
    check("route({'label': 'access'}) == 'access'", route({"label": "access"}) == "access")

    ctx.step("2. Test the whole graph with a fake model")
    for answer, expected in [("network", "network"), ("Access.", "access"), ("no idea", "other")]:
        graph = build_graph(FakeModel(answer))
        result = graph.invoke({"ticket": "any ticket text"})
        check(f"fake model says {answer!r} -> handled_by {expected!r}", result["handled_by"] == expected)

    ctx.step("3. Test that only one branch runs")
    graph = build_graph(FakeModel("hardware"))
    visited = [node for update in graph.stream({"ticket": "x"}, stream_mode="updates") for node in update]
    check(f"visited nodes: {visited}", visited == ["classify", "hardware"])

    ctx.step("4. The same graph against the real model")
    llm = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    class Recording:
        """Wraps the real model so its tokens are counted; same .invoke() shape as the fake."""

        def invoke(self, messages):
            reply = llm.invoke(messages)
            ctx.record_usage(reply.usage_metadata)
            return reply

    real = build_graph(Recording())
    result = real.invoke({"ticket": "Ticket #5311: the office printer on floor 2 is jammed."})
    ctx.show_data("real run", result)
    ctx.note("Not asserted: a real model is not deterministic. That is what evaluation (module 10) is for.")

    ctx.step("Result")
    ctx.note(f"{sum(results)} of {len(results)} checks passed.")
    ctx.note("The fake-model checks run in milliseconds with no network: put them in CI (pytest) as they are.")


if __name__ == "__main__":
    main()
