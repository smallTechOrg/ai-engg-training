"""14.3/1  An MCP server as a crew's toolbox (with a thin bridge)

In 14.1 you gave an agent a Python function with @tool. A crew can also use tools that live on an
MCP server (module 11). CrewAI has a built-in way, Agent(mcps=[MCPServerStdio(...)]). But with the
mcp 2.x package installed here, it builds an EMPTY argument schema. It reads the old camelCase
`inputSchema`, while mcp 2.x calls the field `input_schema`. The model then sees a tool with no
parameters and guesses. This script shows the problem, then fixes it with a bridge of about 15
lines: read the server's tool list yourself, and wrap each tool as a CrewAI BaseTool whose
args_schema is built from the server's real JSON schema.

Run it:   ./run 14.3/1          (Windows: run 14.3/1)
"""

import asyncio
import os
import sys
import threading
from pathlib import Path

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TESTING"] = "true"

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from crewai.mcp import MCPServerStdio  # noqa: E402
from crewai.tools import BaseTool  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from pydantic import create_model  # noqa: E402

from labkit import lesson  # noqa: E402

SERVER = Path(__file__).with_name("asset_server.py")
PARAMS = StdioServerParameters(command=sys.executable, args=[str(SERVER)])


async def _with_session(fn):
    async with stdio_client(PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await fn(session)


def run_async(fn):
    """Run a coroutine to completion from sync code, even if an event loop is already running."""
    box = {}
    thread = threading.Thread(target=lambda: box.update(value=asyncio.run(_with_session(fn))))
    thread.start()
    thread.join()
    return box["value"]


def make_bridge(mcp_tool, calls):
    """Wrap one MCP tool (name, description, input_schema) as a CrewAI tool."""
    props = mcp_tool.input_schema.get("properties", {})
    fields = {name: (str, ...) for name in props}  # this server only has string arguments
    schema = create_model(mcp_tool.name + "_args", **fields)
    tool_name = mcp_tool.name

    class Bridge(BaseTool):
        name: str = tool_name
        description: str = mcp_tool.description or tool_name
        args_schema: type = schema

        def _run(self, **kwargs) -> str:
            result = run_async(lambda s: s.call_tool(tool_name, kwargs))
            text = " ".join(c.text for c in result.content if getattr(c, "text", None))
            calls.append((tool_name, kwargs, text))
            return text

    return Bridge()


def make_llm(ctx):
    return LLM(model=ctx.model, provider="openai", base_url=ctx.settings.base_url,
               api_key=ctx.settings.api_key, temperature=0.2)


@lesson("14.3/1", "An MCP server as a crew's toolbox")
def main(ctx):
    ctx.step("What the MCP server offers (the module 11 way)")
    tools = run_async(lambda s: s.list_tools()).tools
    ctx.show_data("tools/list", [{"name": t.name, "input_schema": t.input_schema} for t in tools])

    ctx.step("CrewAI's built-in mcps=[...] on this install")
    llm = make_llm(ctx)
    probe = Agent(role="Probe", goal="Inspect tools", backstory="Probe.", llm=llm,
                  mcps=[MCPServerStdio(command=sys.executable, args=[str(SERVER)])])
    native = probe.get_mcp_tools(probe.mcps)
    ctx.show_data("schema CrewAI built for the native MCP tool", native[0].args_schema.model_json_schema() if native else "no tools")
    ctx.note("An empty 'properties' means the model is not told that the tool needs a 'tag'. That is a CrewAI 1.6 / mcp 2.x mismatch, so we bridge by hand.")

    ctx.step("Bridge the MCP tools into CrewAI tools")
    calls = []
    bridged = [make_bridge(t, calls) for t in tools]
    ctx.show_data("bridged tool schema", bridged[0].args_schema.model_json_schema())

    agent = Agent(role="Asset checker", goal="Answer questions about company assets using the inventory tool only",
                  backstory="You never guess an asset's health; you look it up.", llm=llm,
                  tools=bridged, allow_delegation=False, max_iter=4)
    task = Task(description="Ticket #5401: Dev's laptop LT-204 loses battery fast. Look up the asset and say whether "
                            "a replacement is justified.",
                expected_output="Two sentences: what the inventory says, and a replace-or-keep recommendation.", agent=agent)

    ctx.step("Run the crew")
    result = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False, tracing=False).kickoff()

    ctx.step("Which MCP calls ran")
    for name, args, text in calls:
        ctx.show_tool_call(name, args, text)
    if not calls:
        ctx.note("The agent did not call the MCP tool this run. Check the answer for guesses.")
    ctx.show_data("Answer", result.raw)

    usage = result.token_usage
    ctx.show_data("requests and tokens", {"successful_requests": usage.successful_requests, "total_tokens": usage.total_tokens})
    if usage.total_tokens:
        ctx.record_usage({"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens})


if __name__ == "__main__":
    main()
