"""14.4/1  Capstone, part 1: the incident-response crew

Three agents in a sequential crew (14.1, 14.2/1), one with a tool (14.1/3):

  Triager (typed Severity output)  ->  Runbook researcher (search_runbook tool)  ->  Comms writer

The brief and acceptance criteria are in the README. This script is the reference crew. Scripts 2
and 3 reuse its shape inside a graph and an acceptance check.

Run it:   ./run 14.4/1          (Windows: run 14.4/1)
"""

import json
import os
from pathlib import Path

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from crewai.tools import tool  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from labkit import lesson  # noqa: E402

RUNBOOK = json.loads(Path(__file__).with_name("runbook.json").read_text(encoding="utf-8"))
INCIDENT = "Since 09:10 nobody in the Berlin office can connect to the VPN. About 40 people are affected."


class Severity(BaseModel):
    severity: str  # low, medium or high
    topic: str  # one word: vpn, email, file server, other
    reason: str


@lesson("14.4/1", "Capstone: the incident-response crew")
def main(ctx):
    @tool("search_runbook")
    def search_runbook(topic: str) -> str:
        """Search the Larkspur Labs runbook. Pass a short topic such as 'vpn', 'email' or 'file server'."""
        key = topic.strip().lower()
        result = next((t for k, t in RUNBOOK.items() if k in key or key in k), "No runbook entry.")
        ctx.show_tool_call("search_runbook", {"topic": topic}, result)
        return result

    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
              api_key=ctx.settings.api_key, temperature=0.2)
    triager = Agent(role="Incident triager", goal="Rate the severity of an incident and name its topic",
                    backstory="High = many people blocked or a deadline at risk. Low = one person, a workaround exists.",
                    llm=llm, allow_delegation=False, max_iter=3)
    researcher = Agent(role="Runbook researcher", goal="Find the runbook steps for the incident",
                       backstory="You only report steps that are in the runbook.", llm=llm,
                       tools=[search_runbook], allow_delegation=False, max_iter=4)
    writer = Agent(role="Comms writer", goal="Write the status message to affected staff",
                   backstory="Calm, factual, short. You always mention the status page.", llm=llm,
                   allow_delegation=False, max_iter=3)

    t1 = Task(description="Triage this incident.\n\n" + INCIDENT, expected_output="severity, topic and a one-line reason",
              agent=triager, output_pydantic=Severity)
    t2 = Task(description="Call search_runbook with the topic from the triage and report the steps.",
              expected_output="The runbook steps, copied.", agent=researcher, context=[t1])
    t3 = Task(description="Write the status message for affected staff using the runbook steps.",
              expected_output="At most four sentences; mentions the status page; says what happens next.",
              agent=writer, context=[t1, t2])

    ctx.step("Run the crew")
    result = Crew(agents=[triager, researcher, writer], tasks=[t1, t2, t3], process=Process.sequential,
                  verbose=False, tracing=False).kickoff()

    ctx.step("Results")
    sev = result.tasks_output[0].pydantic
    ctx.show_data("Severity (typed)", sev.model_dump() if sev else "not parsed: " + result.tasks_output[0].raw)
    ctx.show_data("Status message", result.raw)
    usage = result.token_usage
    ctx.show_data("requests and tokens", {"successful_requests": usage.successful_requests, "total_tokens": usage.total_tokens})
    if usage.total_tokens:
        ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})


if __name__ == "__main__":
    main()
