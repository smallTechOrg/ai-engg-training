"""14.3/2  A crew as one node of a LangGraph graph

LangGraph (modules 08-09) runs the workflow: state, branches, saving progress. CrewAI handles one
step: "have a small team write something". Very little code joins them, because a LangGraph node
is just a function that takes the state and returns an update. Inside it you can call crew.kickoff().

  START -> intake (plain Python) -> crew (CrewAI: drafter + reviewer) -> finish (plain Python) -> END

Use each tool for what it does well: the graph for control flow you can test and resume, the crew
for open-ended writing. The crew here has two tasks, so expect about 3-5 model requests.

Run it:   ./run 14.3/2          (Windows: run 14.3/2)
"""

import os
from typing import TypedDict

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402

from labkit import lesson  # noqa: E402
from labkit.errors import ServiceUnavailable  # noqa: E402

try:
    from langgraph.graph import END, START, StateGraph  # noqa: E402
except ImportError as exc:  # pragma: no cover
    raise ServiceUnavailable("LangGraph is not installed", ["uv sync --extra langgraph"]) from exc

TICKET = "Ticket #5402 from Omar (Finance): the shared scanner on floor 2 says 'toner low' and scans come out faint."


class State(TypedDict, total=False):
    ticket: str
    cleaned: str
    draft: str
    requests_used: int


@lesson("14.3/2", "A crew as one node of a LangGraph graph")
def main(ctx):
    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
              api_key=ctx.settings.api_key, temperature=0.2)

    def intake(state: State) -> dict:
        # Plain Python with no model: it gives the same output every time and is easy to unit test.
        return {"cleaned": " ".join(state["ticket"].split())}

    def crew_node(state: State) -> dict:
        # The whole crew lives inside this one node. Building a fresh crew per call keeps nodes independent.
        drafter = Agent(role="Reply drafter", goal="Draft a short helpdesk reply", backstory="You write for Larkspur Labs IT.",
                        llm=llm, allow_delegation=False, max_iter=3)
        reviewer = Agent(role="Tone reviewer", goal="Make replies calm, kind and at most three sentences",
                         backstory="You edit helpdesk replies.", llm=llm, allow_delegation=False, max_iter=3)
        draft = Task(description="Draft a reply to: " + state["cleaned"], expected_output="A reply of a few sentences.", agent=drafter)
        review = Task(description="Edit the draft: calm tone, at most three sentences, one clear next step.",
                      expected_output="The final reply text only.", agent=reviewer, context=[draft])
        crew = Crew(agents=[drafter, reviewer], tasks=[draft, review], process=Process.sequential, verbose=False, tracing=False)
        result = crew.kickoff()
        usage = result.token_usage
        if usage.total_tokens:
            ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}, quiet=True)
        return {"draft": result.raw, "requests_used": usage.successful_requests}

    def finish(state: State) -> dict:
        return {"draft": state["draft"].strip()}

    ctx.step("Build the graph")
    graph = StateGraph(State)
    graph.add_node("intake", intake)
    graph.add_node("crew", crew_node)
    graph.add_node("finish", finish)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "crew")
    graph.add_edge("crew", "finish")
    graph.add_edge("finish", END)
    app = graph.compile()
    ctx.note("Nodes: intake (python) -> crew (CrewAI) -> finish (python)")

    ctx.step("Stream the graph and watch each node")
    final = {}
    for update in app.stream({"ticket": TICKET}, stream_mode="updates"):
        for node, change in update.items():
            ctx.show_data(f"node '{node}' returned", {k: (v if k != "draft" else str(v)[:160]) for k, v in change.items()})
            final.update(change)

    ctx.step("Final state")
    ctx.show_data("draft", final.get("draft"))
    ctx.note(f"The crew node used {final.get('requests_used')} model request(s); the other two nodes used none.")


if __name__ == "__main__":
    main()
