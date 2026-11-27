"""13.2/2  Replanning when a step fails

Plan-and-execute from 13.2/1 has one weakness: a plan written before anything ran cannot know that
step 4 will fail. The fix is a loop around the executor:

  plan -> run steps -> a step fails -> REPLAN the remaining work given what happened -> keep going

The planner gets the task, the steps already done (with their results) and the failure. MAX_REPLANS
caps the loop so it always ends. A replan is also used for a final "is anything left?" review after
a replanned stretch finishes. When the cap is spent, the run stops and hands over to a person. The
task asks for a laptop that is out of stock, so you should expect a replan.

Run it:   ./run 13.2/2          (Windows: run 13.2/2)
"""

import json

from labkit import lesson

MAX_REPLANS = 3

TASK = (
    "Set up a new starter: Jo Park (Sales) starts on Monday. Create her account, add her to the "
    "all-staff and sales groups, reserve a ThinkBook 14 laptop and send her the welcome email."
)

LAPTOP_STOCK = {"ProBook 15": 3, "ThinkBook 14": 0}


def create_account(full_name: str) -> dict:
    return {"ok": True, "username": full_name.lower().replace(" ", "")[:1] + full_name.split()[-1].lower()}


def add_to_group(full_name: str, group: str) -> dict:
    if group not in {"all-staff", "sales", "finance", "vpn"}:
        return {"ok": False, "error": f"unknown group {group!r}"}
    return {"ok": True, "added": f"{full_name} -> {group}"}


def reserve_laptop(full_name: str, model: str) -> dict:
    if LAPTOP_STOCK.get(model, 0) < 1:
        return {"ok": False, "error": f"{model} is out of stock"}
    return {"ok": True, "reserved": f"{model} for {full_name}"}


def send_welcome_email(full_name: str) -> dict:
    return {"ok": True, "sent_to": full_name}


def list_laptops() -> dict:
    return {"ok": True, "in_stock": {m: n for m, n in LAPTOP_STOCK.items() if n > 0}}


FUNCTIONS = {
    "list_laptops": list_laptops,
    "create_account": create_account,
    "add_to_group": add_to_group,
    "reserve_laptop": reserve_laptop,
    "send_welcome_email": send_welcome_email,
}


def tool(name: str, description: str, props: dict) -> dict:  # props may be empty
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
                "required": list(props),
                "additionalProperties": False,
            },
        },
    }


TOOLS = [
    tool("list_laptops", "List the laptop models that are in stock right now.", {}),
    tool("create_account", "Create a directory account for a new starter.", {"full_name": "Full name, e.g. Alex Example"}),
    tool("add_to_group", "Add an existing account to a group (all-staff, sales, finance, vpn).", {"full_name": "Full name", "group": "Group name"}),
    tool("reserve_laptop", "Reserve a laptop model for a person.", {"full_name": "Full name", "model": "Laptop model, e.g. ProBook 15"}),
    tool("send_welcome_email", "Send the welcome email with first-day instructions.", {"full_name": "Full name"}),
]

# The FIRST JSON object in the planner's prompt only shows the format (a different person and different steps).
PLANNER_SYSTEM = (
    'Write a plan as JSON only, shaped like this example: {"steps": [{"tool": "create_account", "args": {"full_name": "Alex Example"}}, '
    '{"tool": "send_welcome_email", "args": {"full_name": "Alex Example"}}]}\n'
    "Use only these tools and argument names:\n"
    + "\n".join(f"- {t['function']['name']}({', '.join(t['function']['parameters']['properties'])}): {t['function']['description']}" for t in TOOLS)
    + "\nOne step per tool call, in the order they must run."
)


def run_step(name: str, args: dict) -> dict:
    fn = FUNCTIONS.get(name)
    if fn is None:
        return {"ok": False, "error": f"no such tool {name!r}"}
    try:
        return fn(**args)
    except TypeError as exc:
        return {"ok": False, "error": f"bad arguments: {exc}"}



def parse_plan(text: str):
    """Return a list of (tool, args) or None when the reply is not a usable plan."""
    try:
        return [(s["tool"], dict(s["args"])) for s in json.loads(text)["steps"]]
    except (ValueError, KeyError, TypeError):
        return None


@lesson("13.2/2", "Replanning when a step fails")
def main(ctx):
    def ask_for_plan(user_text: str):
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": PLANNER_SYSTEM}, {"role": "user", "content": user_text}],
            response_format={"type": "json_object"},
        )
        ctx.record_usage(response.usage, quiet=True)
        return parse_plan(response.choices[0].message.content or "")

    ctx.step("Make the first plan")
    ctx.note(TASK)
    plan = ask_for_plan(TASK)
    if plan is None:
        ctx.note("The planner did not return a usable plan, so nothing runs. A real system would retry or escalate.")
        return
    ctx.show_data("Plan 1", [{"tool": n, "args": a} for n, a in plan])

    ctx.step("Execute, and replan when a step fails")
    done: list[dict] = []
    replans = 0
    reviewed_after = -1
    outcome = "all steps done"
    while True:
        if not plan:
            if replans == 0 or replans >= MAX_REPLANS or reviewed_after == replans:
                break
            # A replanned stretch has finished: ask once whether anything is still left.
            reviewed_after = replans
            replans += 1
            ctx.note(f"Plan finished after a replan: asking whether anything is left (replan {replans} of {MAX_REPLANS}).")
            plan = ask_for_plan(
                f"Original task: {TASK}\nAlready done: {json.dumps(done)}\n"
                'Write a plan for ONLY what is still left, or {"steps": []} if the task is complete.'
            )
            if plan is None:
                outcome = "stopped: the review did not return a usable plan -> escalate to a human"
                break
            ctx.show_data(f"Plan {replans + 1} (remaining work only)", [{"tool": n, "args": a} for n, a in plan])
            continue
        name, args = plan.pop(0)
        result = run_step(name, args)
        ctx.show_tool_call(name, args, json.dumps(result))
        if result.get("ok"):
            done.append({"tool": name, "args": args, "result": result})
            continue

        if replans >= MAX_REPLANS:
            outcome = f"stopped: {name} failed and the replan cap ({MAX_REPLANS}) is spent -> escalate to a human"
            break
        replans += 1
        ctx.note(f"Step {name} failed ({result['error']}). Replan {replans} of {MAX_REPLANS}.")
        state = (
            f"Original task: {TASK}\n"
            f"Already done (do not repeat): {json.dumps(done)}\n"
            f"Failed step: {json.dumps({'tool': name, 'args': args, 'error': result['error']})}\n"
            "Write a new plan for ONLY the work that is still left. You may use list_laptops to see what is in stock."
        )
        new_plan = ask_for_plan(state)
        if new_plan is None:
            outcome = "stopped: the replanner did not return a usable plan -> escalate to a human"
            break
        plan = new_plan
        ctx.show_data(f"Plan {replans + 1} (remaining work only)", [{"tool": n, "args": a} for n, a in plan])

    ctx.step("Outcome")
    ctx.show_data("Steps that succeeded", [f"{d['tool']} {json.dumps(d['args'])}" for d in done])
    ctx.note(f"Replans used: {replans} of {MAX_REPLANS}. Outcome: {outcome}.")
    ctx.note("The plan changed because of what a step returned. 13.2/3 adds a check that every plan must pass before it runs.")


if __name__ == "__main__":
    main()
