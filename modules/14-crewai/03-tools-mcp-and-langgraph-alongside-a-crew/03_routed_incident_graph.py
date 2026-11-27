"""14.3/3  Scenario: a LangGraph router that calls the crew only when needed

  triage (one plain model call, JSON)
     |-- simple  -> quick_reply (one plain call)
     |-- complex -> crew (CrewAI researcher with a tool + responder)

Crews are the expensive path (many requests per task), so the graph decides when to pay for one.
The conditional edge is ordinary Python on the triage field. The crew's researcher has an
@tool that reads a small invented runbook, as in 14.1.

Run it:   ./run 14.3/3          (Windows: run 14.3/3)
"""

import json
import os
from typing import TypedDict

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from crewai.tools import tool  # noqa: E402

from labkit import lesson  # noqa: E402
from labkit.errors import ServiceUnavailable  # noqa: E402

try:
    from langgraph.graph import END, START, StateGraph  # noqa: E402
except ImportError as exc:  # pragma: no cover
    raise ServiceUnavailable("LangGraph is not installed", ["uv sync --extra langgraph"]) from exc

TICKETS = [
    "Ticket #5410: how do I change my desk phone ringtone?",
    "Ticket #5411: since 08:00 nobody on floor 3 can reach the file server, and the finance close is today.",
]

RUNBOOK = {
    "file server": "File server outage: 1) check the status page, 2) restart the SMB service from the admin console, "
                   "3) if it does not return in 10 minutes page the on-call network engineer.",
    "ringtone": "Ringtones are changed on the phone under Menu > Preferences.",
}


class State(TypedDict, total=False):
    ticket: str
    complexity: str
    reply: str
    path: str


@lesson("14.3/3", "A routed incident graph with a crew branch")
def main(ctx):
    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
              api_key=ctx.settings.api_key, temperature=0.2)

    @tool("search_runbook")
    def search_runbook(topic: str) -> str:
        """Search the Larkspur Labs runbook. Pass a short phrase such as 'file server' or 'ringtone'."""
        key = topic.strip().lower()
        result = next((t for k, t in RUNBOOK.items() if k in key or key in k), "No runbook entry.")
        ctx.show_tool_call("search_runbook", {"topic": topic}, result)
        return result

    def triage(state: State) -> dict:
        response = ctx.client.chat.completions.create(
            model=ctx.model, temperature=0, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": 'Reply with JSON only: {"complexity": "simple" or "complex"}. '
                       "complex = an outage or something affecting many people or a deadline."},
                      {"role": "user", "content": state["ticket"]}])
        ctx.show_response(response)
        try:
            value = json.loads(response.choices[0].message.content or "{}").get("complexity", "")
        except (ValueError, AttributeError):
            value = ""
        return {"complexity": value if value in ("simple", "complex") else "simple"}

    def route(state: State) -> str:
        return "crew" if state["complexity"] == "complex" else "quick_reply"

    def quick_reply(state: State) -> dict:
        response = ctx.client.chat.completions.create(
            model=ctx.model, temperature=0.2,
            messages=[{"role": "system", "content": "You are the Larkspur Labs IT helpdesk. Answer in at most two sentences."},
                      {"role": "user", "content": state["ticket"]}])
        ctx.show_response(response)
        return {"reply": response.choices[0].message.content or "", "path": "quick_reply"}

    def crew_node(state: State) -> dict:
        researcher = Agent(role="Runbook researcher", goal="Find the runbook steps for the incident",
                           backstory="You only report steps that are in the runbook.", llm=llm,
                           tools=[search_runbook], allow_delegation=False, max_iter=4)
        responder = Agent(role="Incident responder", goal="Write the incident reply with the runbook steps",
                          backstory="You write short, urgent but calm replies.", llm=llm, allow_delegation=False, max_iter=3)
        t1 = Task(description="Use search_runbook for this ticket and report the steps.\n\n" + state["ticket"],
                  expected_output="The runbook steps.", agent=researcher)
        t2 = Task(description="Write the reply to the employee using those steps. At most four sentences.",
                  expected_output="The reply.", agent=responder, context=[t1])
        result = Crew(agents=[researcher, responder], tasks=[t1, t2], process=Process.sequential,
                      verbose=False, tracing=False).kickoff()
        usage = result.token_usage
        ctx.note(f"crew finished: {usage.successful_requests} request(s)")
        if usage.total_tokens:
            ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}, quiet=True)
        return {"reply": result.raw, "path": "crew"}

    ctx.step("Build the graph with a conditional edge")
    graph = StateGraph(State)
    graph.add_node("triage", triage)
    graph.add_node("quick_reply", quick_reply)
    graph.add_node("crew", crew_node)
    graph.add_edge(START, "triage")
    graph.add_conditional_edges("triage", route, {"crew": "crew", "quick_reply": "quick_reply"})
    graph.add_edge("quick_reply", END)
    graph.add_edge("crew", END)
    app = graph.compile()

    for ticket in TICKETS:
        ctx.step(ticket[:60])
        out = app.invoke({"ticket": ticket})
        ctx.show_data("result", {"complexity": out["complexity"], "path": out["path"], "reply": out["reply"]})


if __name__ == "__main__":
    main()
