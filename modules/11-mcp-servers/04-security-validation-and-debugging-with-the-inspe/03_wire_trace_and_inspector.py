"""11.4/3  See the wire: raw JSON-RPC by hand, and the MCP Inspector

The MCP Inspector is the official debugging UI: a web page that connects to your server,
lists its tools, lets you fill in arguments and shows the raw messages. It needs Node.js
(`npx`), so this script does not run it. It prints the command, and then does by hand what
the Inspector does: it starts the server, writes JSON-RPC lines to its stdin, and prints
every message in both directions.

No model is needed.

Run it:   ./run 11.4/3          (Windows: run 11.4/3)
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from labkit import lesson

SERVER = Path(__file__).with_name("secure_server.py")


@lesson("11.4/3", "Wire trace and the Inspector")
def main(ctx):
    ctx.step("The MCP Inspector (not run here: it needs Node.js)")
    npx = shutil.which("npx")
    ctx.note(f"npx on this machine: {'found' if npx else 'not found'}")
    ctx.note("Command to try yourself, from the lesson folder:")
    ctx.note(f"  npx @modelcontextprotocol/inspector {Path(sys.executable).name} {SERVER.name}")
    ctx.note("It prints a localhost URL with a session token. Open it, press Connect, then use the Tools / Resources / Prompts tabs.")
    ctx.note("The History pane there shows exactly the messages printed below.")

    ctx.step("Start the server and speak JSON-RPC to it by hand")
    process = subprocess.Popen(
        [sys.executable, str(SERVER)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    try:

        def send(message: dict, expect_reply: bool = True) -> dict | None:
            line = json.dumps(message)
            ctx.note(f"client -> server | {line[:150]}")
            process.stdin.write(line + "\n")
            process.stdin.flush()
            if not expect_reply:
                return None
            reply = json.loads(process.stdout.readline())
            ctx.note(f"server -> client | {json.dumps(reply)[:150]}")
            return reply

        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "by-hand", "version": "0"}},
            }
        )
        send({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_reply=False)
        ctx.note("(notifications have no id and get no reply)")

        tools = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in tools["result"]["tools"]]
        ctx.note(f"tools announced: {names}")

        send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "read_kb_article", "arguments": {"name": "vpn-reset"}}})
        send({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "read_kb_article", "arguments": {"name": "../secrets"}}})
        send({"jsonrpc": "2.0", "id": 5, "method": "no/such/method"})
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    ctx.step("How to read a trace")
    ctx.note("A call that failed validation is still a RESULT with isError true (id 4). The id pairs request and reply.")
    ctx.note("An unknown method is a JSON-RPC ERROR object (id 5), not a result: that is the kind of failure script 2 showed as MCPError.")
    ctx.note("Debug checklist: 1) does initialize succeed? 2) is the tool in tools/list? 3) does the schema match what the model sent? 4) what does stderr say?")


if __name__ == "__main__":
    main()
