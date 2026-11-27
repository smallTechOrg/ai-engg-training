"""14.2/2  Hierarchical process: a manager decides who does what

Sequential: YOU fix the order and the owner of every task.
Hierarchical: you give the crew a goal (tasks with NO agent) and a manager_llm. CrewAI creates a
manager agent that decides which worker gets each task, delegates to it, reviews the answer and
may delegate again. More flexible, but the manager adds model calls and can choose badly.

Cost: a manager round trip per delegation. This script has ONE task and two workers.

Run it:   ./run 14.2/2          (Windows: run 14.2/2)
"""

import os

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from crewai.events import ToolUsageStartedEvent, crewai_event_bus  # noqa: E402

from labkit import lesson  # noqa: E402

TICKET = """Ticket #5302 from Anya (Design):
My laptop battery drains in two hours and the fan is loud. Also, I forgot which portal I use to book a replacement."""


@lesson("14.2/2", "Hierarchical process with a manager")
def main(ctx):
    ctx.step("Workers and a manager model")
    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
              api_key=ctx.settings.api_key, temperature=0.2)
    hardware = Agent(role="Hardware technician", goal="Diagnose laptop hardware problems",
                     backstory="You repair Larkspur Labs laptops and know battery and fan faults.", llm=llm,
                     allow_delegation=False, max_iter=3)
    portal = Agent(role="Portal guide", goal="Explain which internal portal to use for a request",
                   backstory="You know the portals: Self-service (passwords, replacements), IT Desk (hardware swaps), Status page (outages).",
                   llm=llm, allow_delegation=False, max_iter=3)
    ctx.show_data("Workers", [hardware.role, portal.role])

    # No agent= on the task: in a hierarchical crew the manager picks the worker.
    task = Task(description="Prepare one short reply to this ticket that covers every problem in it.\n\n" + TICKET,
                expected_output="A reply of at most five sentences that deals with the hardware fault and the portal question.")

    # Watch which tools run: delegation shows up as the tool "Delegate work to coworker".
    seen = []

    def on_tool(source, event):
        seen.append((event.agent_role, event.tool_name))

    with crewai_event_bus.scoped_handlers():
        crewai_event_bus.on(ToolUsageStartedEvent)(on_tool)

        ctx.step("Run the crew (hierarchical)")
        ctx.note("The manager gets the task, then delegates. Manager and workers all use the same endpoint here.")
        crew = Crew(agents=[hardware, portal], tasks=[task], process=Process.hierarchical,
                    manager_llm=llm, verbose=False, tracing=False)
        result = crew.kickoff()

    ctx.step("What the manager did")
    if seen:
        for role, tool_name in seen:
            ctx.show_tool_call(tool_name, {"by": role}, "(see the crew's answer below)")
    else:
        ctx.note("The manager answered without delegating this run. Hierarchical crews do not guarantee delegation; the model decides.")
    ctx.show_data("Final answer", result.raw)

    ctx.step("Usage")
    usage = result.token_usage
    ctx.show_data("requests and tokens", {"successful_requests": usage.successful_requests, "total_tokens": usage.total_tokens})
    if usage.total_tokens:
        ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})


if __name__ == "__main__":
    main()
