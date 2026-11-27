"""14.1/1  One agent, one task, a crew of one

CrewAI's three nouns in the smallest possible program:

  Agent  a role, a goal and a backstory (these become the system prompt), plus an LLM
  Task   a description of the work and an expected_output (what "done" looks like)
  Crew   the agents and tasks together; crew.kickoff() runs them

By hand (module 01) this was one chat call with a system message. CrewAI wraps it in a
ReAct-style prompt format, so one task can make SEVERAL model calls. This crew of one
usually makes one or two.

Run it:   ./run 14.1/1          (Windows: run 14.1/1)
"""

import os

# Turn CrewAI's telemetry off BEFORE importing it. CREWAI_TESTING also stops the first-run
# "view your execution traces?" prompt, which would otherwise wait 20 seconds for a keypress.
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402

from labkit import lesson  # noqa: E402

TICKET = """Ticket #5201 from Mei (Reception):
The label printer at the front desk prints blank labels since this morning. The visitor
badges are due in 20 minutes."""


@lesson("14.1/1", "One agent, one task, a crew of one")
def main(ctx):
    ctx.step("Point CrewAI at the endpoint")
    # CrewAI talks to models through its LLM class. provider="openai" means "speak the
    # OpenAI-compatible protocol with the openai SDK"; base_url sends it to whatever provider
    # you configured. (With only an "openai/<name>" prefix, CrewAI 1.6 accepts just model names
    # it knows and otherwise needs LiteLLM, which this course does not install.)
    llm = LLM(
        model=ctx.model,
        provider="openai",
        base_url=ctx.settings.base_url,
        api_key=ctx.settings.api_key,
        temperature=0.2,
    )
    ctx.note(f"LLM(model='{ctx.model}', provider='openai', base_url='{ctx.settings.base_url}')")

    ctx.step("Define the agent and the task")
    agent = Agent(
        role="IT helpdesk responder",
        goal="Give an employee a short, calm first reply that tells them what to try first",
        backstory="You work the first line of the Larkspur Labs IT helpdesk and have fixed many label printers.",
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )
    task = Task(
        description="Write the first reply to this ticket:\n\n" + TICKET,
        expected_output="A reply of at most four sentences, ending with one clear next step.",
        agent=agent,
    )
    ctx.show_data("What the agent is", {"role": agent.role, "goal": agent.goal, "backstory": agent.backstory})
    ctx.show_data("What the task is", {"description": task.description, "expected_output": task.expected_output})

    ctx.step("Run the crew")
    ctx.note("A crew of one: crew.kickoff() runs the task. CrewAI may call the model more than once.")
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False, tracing=False)
    result = crew.kickoff()

    ctx.step("Read the result")
    ctx.note("result.raw is the final text. result.token_usage counts every call CrewAI made.")
    ctx.show_data("Output", {"result.raw": result.raw})
    usage = result.token_usage
    ctx.show_data("result.token_usage", usage.model_dump() if hasattr(usage, "model_dump") else str(usage))
    if usage and getattr(usage, "total_tokens", 0):
        ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})
    else:
        ctx.note("This endpoint reported no token usage to CrewAI.")


if __name__ == "__main__":
    main()
