"""14.2/1  Sequential process with a typed hand-off

In 14.1 one task's output reached the next as plain text (context=[...]). Here the first
task returns a PYDANTIC OBJECT (output_pydantic), so your own Python code can read
result.tasks_output[0].pydantic.category instead of parsing a sentence. The second task still
gets the text, because that is all an agent can read.

Sequential means: tasks run in the order of the list, each by the agent it names.
No manager, no choices. Predictable and cheap: two tasks here.

Run it:   ./run 14.2/1          (Windows: run 14.2/1)
"""

import os

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from labkit import lesson  # noqa: E402

TICKET = """Ticket #5301 from Tomas (Sales):
I cannot join the Monday video call from my laptop: the camera shows a black square. Other apps work."""


class Triage(BaseModel):
    category: str  # network, hardware, software, access or other
    urgency: str  # low, normal or high
    summary: str


@lesson("14.2/1", "Sequential process with a typed hand-off")
def main(ctx):
    ctx.step("Model, two agents, two tasks")
    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
              api_key=ctx.settings.api_key, temperature=0.2)
    triager = Agent(role="Ticket triager", goal="Classify a helpdesk ticket",
                    backstory="You sort the Larkspur Labs helpdesk queue.", llm=llm, allow_delegation=False, max_iter=3)
    responder = Agent(role="Helpdesk responder", goal="Write a calm first reply",
                      backstory="You write short, kind replies with one clear next step.", llm=llm, allow_delegation=False, max_iter=3)

    # output_pydantic asks CrewAI to turn the agent's answer into a Triage object. If the model's answer
    # does not fit, CrewAI makes an extra conversion call; if that fails too, .pydantic stays None.
    t1 = Task(description="Triage this ticket.\n\n" + TICKET,
              expected_output="category (network, hardware, software, access or other), urgency (low, normal, high) and a one-line summary",
              agent=triager, output_pydantic=Triage)
    t2 = Task(description="Write the first reply to the employee, matching the urgency of the triage.",
              expected_output="At most three sentences ending with one next step.", agent=responder, context=[t1])
    ctx.show_data("Process", {"process": "sequential", "order": [t1.agent.role, t2.agent.role]})

    ctx.step("Run the crew")
    crew = Crew(agents=[triager, responder], tasks=[t1, t2], process=Process.sequential, verbose=False, tracing=False)
    result = crew.kickoff()

    ctx.step("Use the typed output in Python")
    triage = result.tasks_output[0].pydantic
    if triage is None:
        ctx.note("The triager's answer did not parse into Triage, so .pydantic is None. Fall back to .raw; real code should retry or alert.")
        ctx.show_data("raw triage text", result.tasks_output[0].raw)
    else:
        ctx.show_data("Triage object", triage.model_dump())
        route = "page the on-call" if triage.urgency.lower() == "high" else "normal queue"
        ctx.note(f"Plain Python decision on a typed field: urgency={triage.urgency!r} -> {route}")
    ctx.show_data("Final reply", result.raw)

    ctx.step("Usage")
    usage = result.token_usage
    ctx.show_data("requests and tokens", {"successful_requests": usage.successful_requests, "total_tokens": usage.total_tokens})
    if usage.total_tokens:
        ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})


if __name__ == "__main__":
    main()
