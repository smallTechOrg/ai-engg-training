"""12.3/3  Scenario: a CrewAI agent that uses the helpdesk MCP tools

CrewAI tools are `BaseTool` subclasses with a SYNCHRONOUS `_run`, while an MCP session is async.
The bridge therefore opens a short-lived connection to the server for each tool call
(`asyncio.run` inside `_run`). That costs a server start per call, which is fine for a small
local server and a good reason to keep long-lived sessions for frameworks that are async.
CrewAI can also take MCP servers directly through `Agent(mcps=[...])`; this lesson builds the
bridge by hand so you can see the seam.

CrewAI makes several model requests per task, so the token count comes from CrewAI's own usage report.

Run it:   ./run 12.3/3          (Windows: run 12.3/3)
"""

import asyncio
import os
import sys
from pathlib import Path

# Telemetry off and no trace prompt, BEFORE importing crewai (see 14.1).
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from crewai.tools import BaseTool  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from pydantic import BaseModel, Field, create_model  # noqa: E402

from labkit import lesson  # noqa: E402

SERVER = Path(__file__).with_name("ticket_server.py")
PARAMS = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
TICKET = "T-1002"


async def call_once(name, arguments):
    """Connect, call one tool, disconnect."""
    async with stdio_client(PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            return "".join(p.text for p in result.content if p.type == "text")


def make_crewai_tool(mcp_tool):
    """One MCP tool -> one CrewAI tool. The args model is built from the tool's JSON Schema."""
    fields = {key: (str, Field(description=spec.get("description", key))) for key, spec in mcp_tool.input_schema.get("properties", {}).items()}
    args_model = create_model(f"{mcp_tool.name.title()}Args", __base__=BaseModel, **fields)
    tool_name = mcp_tool.name

    class McpTool(BaseTool):
        name: str = tool_name
        description: str = mcp_tool.description or tool_name
        args_schema: type[BaseModel] = args_model

        def _run(self, **kwargs) -> str:
            return asyncio.run(call_once(tool_name, kwargs))

    return McpTool()


async def list_mcp_tools():
    async with stdio_client(PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return (await session.list_tools()).tools


@lesson("12.3/3", "A CrewAI agent over MCP tools")
async def main(ctx):
    ctx.step("Discover the server's tools and wrap them for CrewAI")
    tools = [make_crewai_tool(t) for t in await list_mcp_tools()]
    for t in tools:
        ctx.note(f"{type(t).__mro__[1].__name__} subclass  name={t.name}  args={list(t.args_schema.model_fields)}")

    ctx.step("Define the agent and the task")
    llm = LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    agent = Agent(
        role="Helpdesk dispatcher",
        goal="Say who should handle a ticket, using the ticket desk tools instead of guessing",
        backstory="You route Larkspur Labs IT tickets to the right owner.",
        tools=tools,
        llm=llm,
        allow_delegation=False,
        verbose=False,
        max_iter=5,
    )
    task = Task(
        description=f"Look up ticket {TICKET} with your tools and say what it is and who owns it.",
        expected_output="Two sentences: the ticket subject, and the owner with their team.",
        agent=agent,
    )
    ctx.step("Run the crew in a worker thread")
    ctx.note("The sync tool calls asyncio.run, which is only safe where no event loop is running: hence to_thread.")
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False, tracing=False)
    result = await asyncio.to_thread(crew.kickoff)

    ctx.step("Result and usage")
    ctx.show_data("result.raw", result.raw)
    usage = result.token_usage
    requests = getattr(usage, "successful_requests", 0)
    ctx.note(f"CrewAI made {requests} model request(s) for one task.")
    if usage and getattr(usage, "total_tokens", 0):
        ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})
    else:
        ctx.note("This endpoint reported no token usage to CrewAI.")
    named = "tomas" in result.raw.lower()  # T-1002 is a hardware ticket; only the server knows its owner
    ctx.note("The answer names the owner the server holds: " + ("yes, so the tool was used." if named else "no, so the tool call probably failed or was skipped."))


if __name__ == "__main__":
    main()
