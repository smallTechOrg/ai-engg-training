"""14.4/2  Capstone, part 2: the crew inside a graph with a guard and a capped retry

  START -> crew -> guard --ok--> END
                     |--bad--> crew (again, with feedback) ... at most 2 crew runs

The guard is plain Python. The status message must mention "status page" and be at most four
sentences. If it fails, the graph sends the crew round again with the problem written into the task
(a cycle, module 09). The cap is the safety net. With a stub model the guard never passes, and the
loop must still end. The crew is small (only the comms writer) to keep the request count low.

Run it:   ./run 14.4/2          (Windows: run 14.4/2)
"""

import os
import re
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

FACTS = ("Incident: email delays since 10:00, about 200 people affected. Runbook: messages are queued, not lost; "
         "the messaging team is escalated after 30 minutes.")
MAX_CREW_RUNS = 2


class State(TypedDict, total=False):
    message: str
    problems: list
    runs: int
    feedback: str


def check(message: str) -> list:
    problems = []
    if "status page" not in message.lower():
        problems.append("does not mention the status page")
    if len([s for s in re.split(r"[.!?]+\s", message.strip()) if s.strip()]) > 4:
        problems.append("is longer than four sentences")
    return problems


@lesson("14.4/2", "The crew in a graph with a guard loop")
def main(ctx):
    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
              api_key=ctx.settings.api_key, temperature=0.2)

    def crew_node(state: State) -> dict:
        runs = state.get("runs", 0) + 1
        writer = Agent(role="Comms writer", goal="Write the status message to affected staff",
                       backstory="Calm, factual, short.", llm=llm, allow_delegation=False, max_iter=3)
        extra = f"\n\nYour previous message was rejected because it {state['feedback']}. Fix that." if state.get("feedback") else ""
        task = Task(description="Write the status message using these facts.\n\n" + FACTS + extra,
                    expected_output="A message for staff of at most four sentences.", agent=writer)
        result = Crew(agents=[writer], tasks=[task], process=Process.sequential, verbose=False, tracing=False).kickoff()
        usage = result.token_usage
        ctx.note(f"crew run {runs}: {usage.successful_requests} request(s)")
        if usage.total_tokens:
            ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}, quiet=True)
        return {"message": result.raw, "runs": runs}

    def guard(state: State) -> dict:
        problems = check(state["message"])
        ctx.show_data(f"guard after run {state['runs']}", {"problems": problems or "none", "message": state["message"][:200]})
        return {"problems": problems, "feedback": " and ".join(problems)}

    def after_guard(state: State) -> str:
        if not state["problems"]:
            return "done"
        if state["runs"] >= MAX_CREW_RUNS:
            ctx.note(f"Cap reached: {MAX_CREW_RUNS} crew runs. Giving up and keeping the last message (a person should review it).")
            return "done"
        return "retry"

    ctx.step("Build and run the graph")
    graph = StateGraph(State)
    graph.add_node("crew", crew_node)
    graph.add_node("guard", guard)
    graph.add_edge(START, "crew")
    graph.add_edge("crew", "guard")
    graph.add_conditional_edges("guard", after_guard, {"done": END, "retry": "crew"})
    out = graph.compile().invoke({"runs": 0})

    ctx.step("Outcome")
    ctx.show_data("final", {"crew_runs": out["runs"], "problems_left": out["problems"] or "none", "message": out["message"]})


if __name__ == "__main__":
    main()
