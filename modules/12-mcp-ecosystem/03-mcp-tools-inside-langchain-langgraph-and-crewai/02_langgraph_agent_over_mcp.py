"""12.3/2  A LangGraph agent that uses MCP tools

New since 12.3/1: instead of one tool call, hand the wrapped MCP tools to `create_agent`
(LangChain 1.x's prebuilt agent, a compiled LangGraph graph) and let it run the whole loop:
model -> tool node -> model -> ... -> answer. The graph is async because MCP sessions are,
so we call `ainvoke`. The tools are the same wrapper as in 12.3/1.

By hand (12.1/2) this loop was about 25 lines of ours; the framework owns it now, and the tools
still come from a server.

Run it:   ./run 12.3/2          (Windows: run 12.3/2)
"""

import sys
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson

SERVER = Path(__file__).with_name("ticket_server.py")
QUESTION = "Find the tickets about Wi-Fi, then tell me who owns the first one."


def text_of(result):
    return "".join(part.text for part in result.content if part.type == "text")


def mcp_tool_to_langchain(session, mcp_tool):
    async def call(**kwargs):
        return text_of(await session.call_tool(mcp_tool.name, kwargs))

    return StructuredTool(name=mcp_tool.name, description=mcp_tool.description or mcp_tool.name, args_schema=mcp_tool.input_schema, coroutine=call)


@lesson("12.3/2", "A LangGraph agent over MCP tools")
async def main(ctx):
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = [mcp_tool_to_langchain(session, t) for t in (await session.list_tools()).tools]

            ctx.step("Build the agent from MCP tools")
            model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
            agent = create_agent(model, tools=tools, system_prompt="You are the Larkspur Labs helpdesk assistant. Use the tools; do not guess. Be brief.")
            ctx.note(f"Tools: {', '.join(t.name for t in tools)}. The agent is a compiled graph: {type(agent).__name__}.")

            ctx.step("Run it (recursion_limit 9 caps the loop)")
            try:
                result = await agent.ainvoke({"messages": [("user", QUESTION)]}, {"recursion_limit": 9})
            except Exception as exc:  # hitting the cap is an outcome, not a crash
                ctx.note(f"Stopped: {type(exc).__name__}: {str(exc)[:140]}")
                return

            ctx.step("Read the trace in the message list")
            for m in result["messages"]:
                if m.type == "ai":
                    ctx.record_usage(m.usage_metadata, quiet=True)
                    for call in m.tool_calls:
                        ctx.note(f"model asks  : {call['name']}({call['args']})")
                elif m.type == "tool":
                    ctx.note(f"tool answers: {m.content}")
            ctx.note(f"{len(result['messages'])} messages in total (human, AI tool calls, tool results, final AI).")
            ctx.step("Final answer")
            ctx.note(str(result["messages"][-1].content))


if __name__ == "__main__":
    main()
