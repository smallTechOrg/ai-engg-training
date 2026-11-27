"""14.2/3  Delegation inside a sequential crew

Delegation is not only for hierarchical crews. Give an agent allow_delegation=True and CrewAI adds
two tools to it: "Delegate work to coworker" and "Ask question to coworker". The agent may call
them to hand a sub-question to another agent in the same crew. Whether it does is up to the model.

The script prints the tools each agent really received, then runs one task and reports whether
a delegation happened. Compare allow_delegation=False: no such tools, no possibility.

Run it:   ./run 14.2/3          (Windows: run 14.2/3)
"""

import os

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from crewai.events import ToolUsageStartedEvent, crewai_event_bus  # noqa: E402

from labkit import lesson  # noqa: E402

TICKET = """Ticket #5303 from Lena (Legal):
I need access to the shared contracts folder, and my security key stopped working this morning."""


@lesson("14.2/3", "Delegation in a sequential crew")
def main(ctx):
    ctx.step("A lead who may delegate, and a specialist who may not")
    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
              api_key=ctx.settings.api_key, temperature=0.2)
    lead = Agent(role="Helpdesk lead", goal="Answer the whole ticket, asking a specialist when a part is outside your knowledge",
                 backstory="You run the first line. For security-key faults you ask the Identity specialist.",
                 llm=llm, allow_delegation=True, max_iter=4)
    identity = Agent(role="Identity specialist", goal="Answer questions about security keys and folder access",
                     backstory="Facts you know: a dead key is replaced at the IT Desk with photo ID within one day; "
                               "folder access needs approval from the folder owner in the Self-service portal.",
                     llm=llm, allow_delegation=False, max_iter=3)
    ctx.show_data("allow_delegation", {lead.role: lead.allow_delegation, identity.role: identity.allow_delegation})

    task = Task(description="Reply to this ticket.\n\n" + TICKET,
                expected_output="A reply of at most four sentences covering both problems.", agent=lead)

    seen = []

    def on_tool(source, event):
        seen.append((event.agent_role, event.tool_name, event.tool_args))

    with crewai_event_bus.scoped_handlers():
        crewai_event_bus.on(ToolUsageStartedEvent)(on_tool)
        ctx.step("Run the crew (identity is in the crew but owns no task)")
        crew = Crew(agents=[lead, identity], tasks=[task], process=Process.sequential, verbose=False, tracing=False)
        result = crew.kickoff()

    ctx.step("Did a delegation happen?")
    if seen:
        for role, name, args in seen:
            ctx.show_tool_call(name, {"agent": role, "args": str(args)[:200]}, "ok")
    else:
        ctx.note("No delegation this run: the lead answered alone. Delegation is a model decision, so design for both outcomes.")
    ctx.show_data("Final reply", result.raw)

    ctx.step("Usage")
    usage = result.token_usage
    ctx.show_data("requests and tokens", {"successful_requests": usage.successful_requests, "total_tokens": usage.total_tokens})
    if usage.total_tokens:
        ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})


if __name__ == "__main__":
    main()
