"""11.2/3  Prompts: user-selected templates with arguments

A prompt is a template the USER picks (think slash command). `prompts/get` fills it in
and returns ready-made chat messages. This script lists the prompt with its argument
metadata, renders it two ways, shows the error for a missing argument, and finally
combines a prompt and a resource, which is how a host builds a context-rich request.
The last step only builds the messages (no model call), so no endpoint is needed.

Run it:   ./run 11.2/3          (Windows: run 11.2/3)
"""

import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from labkit import lesson

SERVER = Path(__file__).with_name("ticket_server.py")


@lesson("11.2/3", "Prompts with arguments")
async def main(ctx):
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    with open(os.devnull, "w") as quiet:
        async with stdio_client(params, errlog=quiet) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                ctx.step("What a client sees when it lists prompts")
                for prompt in (await session.list_prompts()).prompts:
                    ctx.show_data(
                        f"prompt: {prompt.name}",
                        {"description": prompt.description, "arguments": [a.model_dump(exclude_none=True) for a in prompt.arguments or []]},
                    )
                ctx.note("A UI can build a form from this: one field per argument, a star on the required ones.")
                ctx.note("Unlike a tool schema, the listing carries only names and required flags: no types, no enum for `audience`.")

                ctx.step("Render the same prompt for two audiences")
                text = "My badge does not open the server room."
                for audience in ("agent", "customer"):
                    got = await session.get_prompt("triage_prompt", {"ticket_text": text, "audience": audience})
                    for message in got.messages:
                        ctx.show_messages([{"role": message.role, "content": message.content.text}])

                ctx.step("A missing required argument, and a value the function rejects")
                for args in ({}, {"ticket_text": "x", "audience": "bogus"}):
                    try:
                        await session.get_prompt("triage_prompt", args)
                    except MCPError as exc:
                        ctx.note(f"get_prompt({args}) -> MCPError: {exc}")
                ctx.note("The server still validates against the Python types; the client just cannot see them in the listing.")

                ctx.step("Compose: prompt + resource = the messages a host would send")
                ticket = await session.read_resource("helpdesk://tickets/T-1001")
                prompt = await session.get_prompt("triage_prompt", {"ticket_text": "VPN drops every ten minutes"})
                messages = [
                    {"role": "system", "content": "You are the Larkspur Labs IT helpdesk assistant."},
                    {"role": "user", "content": "Reference record:\n" + ticket.contents[0].text},
                    {"role": prompt.messages[0].role, "content": prompt.messages[0].content.text},
                ]
                ctx.show_messages(messages)
                ctx.note("The resource gives context, the prompt gives the instruction, the host decides the order.")
                ctx.note("From here it is an ordinary chat call (see 11.3 for a host that does this with a model).")


if __name__ == "__main__":
    main()
