"""14.4/3  Capstone, part 3: acceptance criteria as code

This script turns the README's acceptance criteria into checks that run on a crew's output and print
a pass/fail table. The crew handles one incident. It has a triager with typed output and a comms
writer, and no tool, so the cost stays low. The checks cover the typed field, the message and the
request budget.

Passing is not the goal. A failed row tells you which criterion to improve, and the checks run
unchanged if you swap in a stronger crew.

Run it:   ./run 14.4/3          (Windows: run 14.4/3)
"""

import os

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from labkit import lesson  # noqa: E402

INCIDENT = "The finance file server has been unreachable since 08:00; month-end close is today. About 15 people are blocked."
REQUEST_BUDGET = 8


class Severity(BaseModel):
    severity: str  # low, medium or high
    reason: str


@lesson("14.4/3", "Acceptance criteria as code")
def main(ctx):
    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
              api_key=ctx.settings.api_key, temperature=0.2)
    triager = Agent(role="Incident triager", goal="Rate incident severity as low, medium or high",
                    backstory="High = many people blocked or a deadline at risk.", llm=llm, allow_delegation=False, max_iter=3)
    writer = Agent(role="Comms writer", goal="Write the status message to affected staff",
                   backstory="Calm, factual, short. You always mention the status page.", llm=llm,
                   allow_delegation=False, max_iter=3)
    t1 = Task(description="Triage this incident.\n\n" + INCIDENT, expected_output="severity and a one-line reason",
              agent=triager, output_pydantic=Severity)
    t2 = Task(description="Write the status message for the affected staff.", expected_output="At most four sentences; mentions the status page.",
              agent=writer, context=[t1])

    ctx.step("Run the crew")
    result = Crew(agents=[triager, writer], tasks=[t1, t2], process=Process.sequential, verbose=False, tracing=False).kickoff()
    sev = result.tasks_output[0].pydantic
    message = result.raw
    usage = result.token_usage

    ctx.step("Acceptance checks")
    checks = [
        ("typed severity parsed", sev is not None),
        ("severity is low/medium/high", bool(sev) and sev.severity.strip().lower() in ("low", "medium", "high")),
        ("deadline incident rated high", bool(sev) and sev.severity.strip().lower() == "high"),
        ("message mentions the status page", "status page" in message.lower()),
        ("message at most four sentences", len([s for s in message.replace("\n", " ").split(". ") if s.strip()]) <= 4),
        (f"requests within budget ({usage.successful_requests} <= {REQUEST_BUDGET})", usage.successful_requests <= REQUEST_BUDGET),
    ]
    for name, ok in checks:
        ctx.note(("PASS  " if ok else "FAIL  ") + name)
    passed = sum(1 for _, ok in checks if ok)
    ctx.show_data("Score", {"passed": passed, "total": len(checks), "message": message})
    if passed < len(checks):
        ctx.note("Some checks failed. With a real model, the failed rows show what to improve next. With the stub, failing is expected.")
    if usage.total_tokens:
        ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})


if __name__ == "__main__":
    main()
