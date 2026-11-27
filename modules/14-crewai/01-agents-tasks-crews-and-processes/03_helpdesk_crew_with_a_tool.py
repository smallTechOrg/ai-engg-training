"""14.1/3  Scenario: a three-agent helpdesk crew with a tool

  Triager  ->  Researcher (uses a lookup tool on an invented KB)  ->  Responder

The researcher is the only agent with a tool. CrewAI turns the tool's name, description and
type hints into the schema the model sees, runs it when the model asks, and feeds the result
back, which is the loop you wrote by hand in module 02. Our tool prints each call so you can
see it happen.

Cost warning: CrewAI makes several model calls per task (a tool round trip alone is two, and CrewAI adds formatting retries).
A real run of this crew made about a dozen requests (see successful_requests). max_iter caps each agent's loop.

Run it:   ./run 14.1/3          (Windows: run 14.1/3)
"""

import os

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"  # also stops the first-run "view traces?" prompt

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from crewai.tools import tool  # noqa: E402

from labkit import lesson  # noqa: E402

TICKET = """Ticket #5212 from Priya (Finance):
My second monitor flickers every few minutes. I tried a different cable and it is the same."""

KB = {
    "monitor": "Flicker on a second monitor: check the refresh rate is 60 Hz in display settings, update the dock firmware, "
               "then swap the dock. Hardware swaps are booked at the IT desk.",
    "vpn": "VPN sessions last 8 hours. Sign in again with your security key.",
    "password": "Reset your password in the self-service portal. If you lost your security key too, open a ticket.",
}


@lesson("14.1/3", "Three-agent helpdesk crew")
def main(ctx):
    calls = []

    # @tool turns a function into something an agent can call. The docstring is the
    # description the model reads, and the type hints become the argument schema.
    @tool("search_kb")
    def search_kb(topic: str) -> str:
        """Search the Larkspur Labs knowledge base. Pass one keyword such as 'monitor', 'vpn' or 'password'."""
        key = topic.strip().lower()
        hit = next((text for word, text in KB.items() if word in key or key in word), None)
        result = hit or "No article found."
        calls.append((topic, result))
        ctx.show_tool_call("search_kb", {"topic": topic}, result)
        return result

    ctx.step("Create the model object and the three agents")
    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
              api_key=ctx.settings.api_key, temperature=0.2)
    triager = Agent(role="Ticket triager", goal="Classify the ticket and name its main topic in one word",
                    backstory="You sort the Larkspur Labs helpdesk queue.", llm=llm, allow_delegation=False, max_iter=3)
    researcher = Agent(role="KB researcher", goal="Find the knowledge base article that applies to the ticket",
                       backstory="You know the knowledge base and never invent steps that are not in it.",
                       llm=llm, tools=[search_kb], allow_delegation=False, max_iter=4)
    responder = Agent(role="Helpdesk responder", goal="Write a calm first reply that uses the researched steps",
                      backstory="You write short, kind replies with a clear next step.", llm=llm, allow_delegation=False, max_iter=3)

    ctx.step("Three tasks, each building on the last")
    t1 = Task(description="Triage this ticket: give the category and the one-word topic.\n\n" + TICKET,
              expected_output="One line: 'Category: ..., Topic: ...'", agent=triager)
    t2 = Task(description="Use the search_kb tool with the topic from the triage. Report the article text you found.",
              expected_output="The knowledge base steps that apply, copied from the article.", agent=researcher, context=[t1])
    t3 = Task(description="Write the first reply to the employee in the ticket, using only the researched steps.",
              expected_output="A reply of at most five sentences ending with one next step.", agent=responder, context=[t1, t2])
    ctx.show_data("Crew", {"agents": [a.role for a in (triager, researcher, responder)], "tools on the researcher": ["search_kb"]})

    ctx.step("Run the crew")
    ctx.note("Several model calls per task: this takes a little while.")
    crew = Crew(agents=[triager, researcher, responder], tasks=[t1, t2, t3],
                process=Process.sequential, verbose=False, tracing=False)
    result = crew.kickoff()

    ctx.step("What each agent produced")
    for task_output in result.tasks_output:
        ctx.show_data(task_output.agent, task_output.raw)
    if not calls:
        ctx.note("The researcher never called search_kb this run. Models sometimes skip a tool; its answer then comes from the model alone.")

    ctx.step("Usage")
    usage = result.token_usage
    ctx.show_data("result.token_usage", usage.model_dump() if hasattr(usage, "model_dump") else str(usage))
    if usage and getattr(usage, "total_tokens", 0):
        ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})
    ctx.note("Compare with the by-hand version: three chat calls plus a tool loop. The crew trades extra calls for structure.")


if __name__ == "__main__":
    main()
