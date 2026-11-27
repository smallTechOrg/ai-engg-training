"""12.3/1  Wrap MCP tools as LangChain tools

The langchain-mcp-adapters package does this for you, but it is not part of this course's
install, and the wrapper is small enough to read. For each MCP tool we build a LangChain
`StructuredTool` whose `coroutine` calls `session.call_tool`. MCP already describes arguments as
JSON Schema, and LangChain accepts a JSON Schema dict as `args_schema`, so nothing is converted.

Then ChatOpenAI.bind_tools turns those tools into a tool-calling request, as in module 07.

Run it:   ./run 12.3/1          (Windows: run 12.3/1)
"""

import sys
from pathlib import Path

from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from labkit import lesson

SERVER = Path(__file__).with_name("ticket_server.py")


def text_of(result):
    return "".join(part.text for part in result.content if part.type == "text")


def mcp_tool_to_langchain(session, mcp_tool):
    """One MCP tool -> one LangChain tool. Calling it forwards the call to the server."""

    async def call(**kwargs):
        return text_of(await session.call_tool(mcp_tool.name, kwargs))

    return StructuredTool(
        name=mcp_tool.name,
        description=mcp_tool.description or mcp_tool.name,
        args_schema=mcp_tool.input_schema,  # a JSON Schema dict is accepted as-is
        coroutine=call,
    )


@lesson("12.3/1", "MCP tools as LangChain tools")
async def main(ctx):
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            ctx.step("Wrap every MCP tool as a LangChain tool")
            tools = [mcp_tool_to_langchain(session, t) for t in (await session.list_tools()).tools]
            for t in tools:
                ctx.note(f"{type(t).__name__}  name={t.name}  args={list(t.args)}")
            ctx.note("These look exactly like tools made with @tool in module 07, but the body is a call to a server.")

            ctx.step("Call one as LangChain would")
            args = {"ticket_id": "T-1001"}
            ctx.show_tool_call("lookup", args, await tools[0].ainvoke(args))

            ctx.step("Let a chat model pick a tool")
            model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
            reply = await model.bind_tools(tools).ainvoke("Who owns ticket T-1004 and what is it about?")
            ctx.record_usage(reply.usage_metadata)
            ctx.note(f"AIMessage text: {reply.content!r}")
            for call in reply.tool_calls:
                ctx.note(f"The model asked for: {call['name']}({call['args']})")
                by_name = {t.name: t for t in tools}
                ctx.show_tool_call(call["name"], call["args"], await by_name[call["name"]].ainvoke(call["args"]))
            if not reply.tool_calls:
                ctx.note("The model answered without calling a tool. Try a more direct question.")


if __name__ == "__main__":
    main()
