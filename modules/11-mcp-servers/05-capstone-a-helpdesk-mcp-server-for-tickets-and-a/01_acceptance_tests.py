"""11.5/1  Acceptance tests for the helpdesk MCP server, end to end over stdio

The capstone server (`helpdesk_server.py`) is only done when a client can prove it. This
script is that client: a checklist of behaviours (discovery, validation, state changes,
resources, prompts, annotations, logs), each a PASS or FAIL line. No model is involved, so
it runs in a second and is the first thing to run after any change to the server.

Exit status is 0 when every check passes, 1 otherwise.

Run it:   ./run 11.5/1          (Windows: run 11.5/1)
"""

import json
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from labkit import lesson

SERVER = Path(__file__).with_name("helpdesk_server.py")


def text_of(result) -> str:
    return "".join(p.text for p in result.content if p.type == "text")


@lesson("11.5/1", "Acceptance tests over stdio")
async def main(ctx):
    results: list[tuple[str, bool]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok))
        ctx.note(f"{'PASS' if ok else 'FAIL'} | {name}" + (f"  ({detail})" if detail and not ok else ""))

    with tempfile.TemporaryFile("w+", encoding="utf-8") as errlog:
        params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
        async with stdio_client(params, errlog=errlog) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=15) as session:
                init = await session.initialize()

                ctx.step("Discovery")
                caps = init.capabilities
                check("announces tools, resources and prompts", bool(caps.tools and caps.resources and caps.prompts))
                tools = {t.name: t for t in (await session.list_tools()).tools}
                expected = {"search_tickets", "get_ticket", "create_ticket", "update_ticket_status", "find_assets", "assign_asset"}
                check("exposes the six agreed tools", set(tools) == expected, str(sorted(tools)))
                check("every tool has a description", all(t.description for t in tools.values()))
                check("only update_ticket_status is destructive", [n for n, t in tools.items() if t.annotations and t.annotations.destructive_hint] == ["update_ticket_status"])
                templates = [t.uri_template for t in (await session.list_resource_templates()).resource_templates]
                check("offers ticket and asset resource templates", sorted(templates) == ["helpdesk://assets/{tag}", "helpdesk://tickets/{ticket_id}"], str(templates))
                prompts = [p.name for p in (await session.list_prompts()).prompts]
                check("offers triage_prompt and handover_summary", sorted(prompts) == ["handover_summary", "triage_prompt"], str(prompts))

                ctx.step("Reading")
                found = text_of(await session.call_tool("search_tickets", {"category": "network"}))
                check("search_tickets filters by category", "T-3001" in found and "T-3002" not in found, found)
                detail = text_of(await session.call_tool("get_ticket", {"ticket_id": "T-3004"}))
                check("get_ticket wraps user text as untrusted", "<untrusted>" in detail and "</untrusted>" in detail)
                laptops = text_of(await session.call_tool("find_assets", {"kind": "laptop"}))
                check("find_assets hides assets in repair", "LL-L-0412" not in laptops and "LL-L-0500" in laptops, laptops)

                ctx.step("Validation and expected failures")
                for name, args, why in [
                    ("create_ticket", {"subject": "x", "category": "network", "requester": "mara.k"}, "subject too short"),
                    ("create_ticket", {"subject": "Valid subject", "category": "printers", "requester": "mara.k"}, "category not in enum"),
                    ("create_ticket", {"subject": "Valid subject", "category": "network", "requester": "Mara K"}, "requester handle pattern"),
                    ("get_ticket", {"ticket_id": "3001"}, "id pattern"),
                    ("assign_asset", {"tag": "LL-L-0412", "assignee": "mara.k"}, "asset in repair"),
                    ("assign_asset", {"tag": "LL-L-9999", "assignee": "mara.k"}, "unknown asset"),
                ]:
                    result = await session.call_tool(name, args)
                    check(f"{name} rejects: {why}", result.is_error, text_of(result)[:60])

                ctx.step("State changes")
                created = text_of(await session.call_tool("create_ticket", {"subject": "Dock does not charge", "category": "hardware", "requester": "dev.p"}))
                check("create_ticket returns the next id", created.startswith("Created T-3006"), created)
                as_resource = json.loads((await session.read_resource("helpdesk://tickets/T-3006")).contents[0].text)
                check("the new ticket is readable as a resource", as_resource["subject"] == "Dock does not charge", str(as_resource))
                assigned = await session.call_tool("assign_asset", {"tag": "LL-L-0500", "assignee": "mara.k"})
                check("assign_asset assigns an available laptop", not assigned.is_error, text_of(assigned))
                second = await session.call_tool("assign_asset", {"tag": "LL-L-0500", "assignee": "joel.t"})
                check("a second assignment of the same asset is refused", second.is_error, text_of(second))
                asset = json.loads((await session.read_resource("helpdesk://assets/LL-L-0500")).contents[0].text)
                check("asset resource shows the first assignee", asset["assigned_to"] == "mara.k", str(asset))

                ctx.step("Resources and prompts")
                policy = (await session.read_resource("helpdesk://policies/hardware")).contents[0].text
                check("hardware policy resource mentions batteries", "battery" in policy.lower() or "batteries" in policy.lower())
                try:
                    await session.read_resource("helpdesk://tickets/T-0000")
                    check("unknown ticket resource raises MCPError", False)
                except MCPError:
                    check("unknown ticket resource raises MCPError", True)
                got = await session.get_prompt("triage_prompt", {"ticket_text": "Badge reader rejects me"})
                check("triage_prompt embeds the ticket text", "Badge reader rejects me" in got.messages[0].content.text)

        errlog.seek(0)
        log_events = []
        for line in errlog.read().splitlines():
            try:
                log_events.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # SDK's own log lines

    ctx.step("Logs")
    tool_logs = [e for e in log_events if e.get("event") == "tool"]
    check("server logged JSON lines to stderr", bool(log_events) and log_events[0]["event"] == "server_start")
    check("rejections were logged with a reason", any(e.get("outcome") == "rejected" and e.get("reason") for e in tool_logs))
    check("no argument values leaked into logs", "mara.k" not in json.dumps(log_events))

    passed = sum(ok for _, ok in results)
    ctx.step("Result")
    ctx.note(f"{passed} of {len(results)} checks passed.")
    if passed != len(results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
