"""08.3/2  Visualising a graph

A compiled graph can describe itself. This lesson draws the 08.2 router graph four ways:
Mermaid text (for READMEs and docs), a Mermaid file written to a temp folder, the nodes and
edges as data (for your own tooling), and an ASCII sketch if the optional drawing package
is installed. No model is called: the structure alone is enough.

Run it:   ./run 08.3/2          (Windows: run 08.3/2)
"""

import tempfile
from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from labkit import lesson


class State(TypedDict, total=False):
    ticket: str
    label: str
    answer: str


def classify(state: State) -> Command[Literal["hardware", "access", "network", "other"]]:
    return Command(update={"label": "other"}, goto="other")


def make(name):
    return lambda state: {"answer": f"handled by {name}"}


def build():
    builder = StateGraph(State)
    builder.add_node("classify", classify)
    for name in ("hardware", "access", "network", "other"):
        builder.add_node(name, make(name))
        builder.add_edge(name, END)
    builder.add_edge(START, "classify")
    return builder.compile()


@lesson("08.3/2", "Visualising a graph")
def main(ctx):
    graph = build()
    drawable = graph.get_graph()  # a description of the structure, separate from the runnable

    ctx.step("Nodes and edges as data")
    ctx.show_data("nodes", list(drawable.nodes))
    ctx.show_data(
        "edges",
        [{"from": e.source, "to": e.target, "conditional": e.conditional} for e in drawable.edges],
    )

    ctx.step("Mermaid text")
    mermaid = drawable.draw_mermaid()
    ctx.console.print(mermaid, markup=False, highlight=False)
    ctx.note("Dotted arrows are conditional edges. GitHub, GitLab and most docs tools render a ```mermaid block.")

    ctx.step("Write it to a file")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "helpdesk_router.mmd"
        path.write_text(mermaid, encoding="utf-8")
        ctx.note(f"wrote {path.name}: {path.stat().st_size} bytes (temp folder, removed afterwards)")

    ctx.step("An ASCII sketch for the terminal")
    try:
        ctx.console.print(drawable.draw_ascii(), markup=False, highlight=False)
    except ImportError as exc:
        ctx.note(f"draw_ascii needs the optional 'grandalf' package ({exc.__class__.__name__}); skipping.")
        ctx.note("Install it with `uv pip install grandalf` to try it.")

    ctx.step("PNG rendering exists, but needs a renderer")
    ctx.note("draw_mermaid_png() calls a web renderer by default, so it needs internet access. Not run here.")
    ctx.note("Rule of thumb: commit the Mermaid text, let the docs site render it.")


if __name__ == "__main__":
    main()
