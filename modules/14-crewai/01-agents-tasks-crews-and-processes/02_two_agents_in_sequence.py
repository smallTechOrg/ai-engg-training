"""14.1/2  Two agents in sequence: triager, then responder

Two agents, two tasks, Process.sequential. Tasks run in the order listed. The second task
declares context=[first_task], so CrewAI puts the first task's output into the second
task's prompt. That is the whole "hand-off": there is no shared memory, only that text.

By hand (modules 01 and 02) you would call the model once for the triage, paste the result
into the next messages list and call it again. CrewAI does that pasting for you.

Each task can cost more than one model call, so this crew makes a small handful of calls.

Run it:   ./run 14.1/2          (Windows: run 14.1/2)
"""

import os

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"  # also stops the first-run "view traces?" prompt

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402

from labkit import lesson  # noqa: E402

TICKET = """Ticket #5207 from Dana (Sales):
I was locked out of my account after the holiday and now my laptop will not connect to the
office Wi-Fi either. I have a customer call at 2pm."""


@lesson("14.1/2", "Two agents in sequence")
def main(ctx):
    ctx.step("Create the model object once and share it")
    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
              api_key=ctx.settings.api_key, temperature=0.2)

    ctx.step("Define two agents and two tasks")
    triager = Agent(
        role="Ticket triager",
        goal="Classify a helpdesk ticket and say how urgent it is",
        backstory="You sort the Larkspur Labs helpdesk queue. You are brief and never guess at fixes.",
        llm=llm, allow_delegation=False,
    )
    responder = Agent(
        role="Helpdesk responder",
        goal="Write a calm, useful first reply to the employee",
        backstory="You write the replies employees actually read: short, kind, one next step.",
        llm=llm, allow_delegation=False,
    )
    triage_task = Task(
        description="Triage this ticket. Give the category (network, hardware, software or access) and urgency (low, medium, high), with one line of reasoning.\n\n" + TICKET,
        expected_output="Two lines: 'Category: ... Urgency: ...' and 'Reason: ...'.",
        agent=triager,
    )
    reply_task = Task(
        description="Using the triage, write the first reply to the employee in the ticket.",
        expected_output="A reply of at most four sentences that acknowledges the deadline and ends with one next step.",
        agent=responder,
        context=[triage_task],  # the triage output is added to this task's prompt
    )
    ctx.show_data("The hand-off", {
        "task 1": triage_task.agent.role,
        "task 2": reply_task.agent.role,
        "task 2 context": [t.agent.role + "'s task" for t in reply_task.context],
    })

    ctx.step("Run the crew (sequential)")
    ctx.note("Process.sequential runs the tasks in list order. Expect a few model calls in total.")
    crew = Crew(agents=[triager, responder], tasks=[triage_task, reply_task],
                process=Process.sequential, verbose=False, tracing=False)
    result = crew.kickoff()

    ctx.step("Read each task's output")
    for task_output in result.tasks_output:
        ctx.show_data(f"Output of the {task_output.agent} task", task_output.raw)
    ctx.note("The final result is the last task's output: result.raw")

    ctx.step("Usage")
    usage = result.token_usage
    ctx.show_data("result.token_usage", usage.model_dump() if hasattr(usage, "model_dump") else str(usage))
    if usage and getattr(usage, "total_tokens", 0):
        ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})
    else:
        ctx.note("This endpoint reported no token usage to CrewAI.")


if __name__ == "__main__":
    main()
