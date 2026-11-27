"""13.2/1  Two ways to run a multi-step task: ReAct and plan-and-execute

The task is a new-starter set-up with four steps. We run it twice with the same simulated tools:

  A. ReAct: the model picks ONE tool call at a time, sees the result, then picks the next.
     Every step costs a model call, but the model can adapt after each result.
  B. Plan-and-execute: the model writes the WHOLE plan up front (JSON), plain Python runs the
     steps, and one more call summarises. Fewer calls and a plan you can inspect before anything
     runs, but the plan cannot react to what the steps return (script 2 fixes that).

Both runs are counted so you can compare cost. Both have hard caps.

Run it:   ./run 13.2/1          (Windows: run 13.2/1)
"""

import json

from labkit import lesson

MAX_REACT_TURNS = 8

TASK = (
    "Set up a new starter: Jo Park (Sales) starts on Monday. Create her account, add her to the "
    "all-staff and sales groups, reserve a ProBook 15 laptop and send her the welcome email."
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


FUNCTIONS = {
    "create_account": create_account,
    "add_to_group": add_to_group,
    "reserve_laptop": reserve_laptop,
    "send_welcome_email": send_welcome_email,
}


def tool(name: str, description: str, props: dict) -> dict:
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
    tool("create_account", "Create a directory account for a new starter.", {"full_name": "Full name, e.g. Alex Example"}),
    tool("add_to_group", "Add an existing account to a group (all-staff, sales, finance, vpn).", {"full_name": "Full name", "group": "Group name"}),
    tool("reserve_laptop", "Reserve a laptop model for a person.", {"full_name": "Full name", "model": "Laptop model, e.g. ProBook 15"}),
    tool("send_welcome_email", "Send the welcome email with first-day instructions.", {"full_name": "Full name"}),
]

# The FIRST JSON object in the planner's prompt is a format example (different person, different steps).
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


@lesson("13.2/1", "ReAct versus plan-and-execute")
def main(ctx):
    ctx.step("The task and the tools")
    ctx.note(TASK)
    ctx.note("Tools: " + ", ".join(FUNCTIONS) + " (all simulated, nothing real changes).")

    # ---- A. ReAct ----
    ctx.step("A. ReAct: one tool call at a time")
    messages = [
        {"role": "system", "content": "You are the Larkspur Labs IT assistant. Use the tools to do the task, one step at a time. Finish with one sentence saying what is done."},
        {"role": "user", "content": TASK},
    ]
    react_calls = 0
    react_steps = 0
    answer = None
    for turn in range(1, MAX_REACT_TURNS + 1):
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=TOOLS)
        react_calls += 1
        message = response.choices[0].message
        if not message.tool_calls:
            answer = ctx.show_response(response)  # records the usage of the final reply
            break
        ctx.record_usage(response.usage, quiet=True)
        messages.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except ValueError:
                args = {}
            result = run_step(call.function.name, args)
            react_steps += 1
            ctx.show_tool_call(call.function.name, args, json.dumps(result))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    if answer is None:
        ctx.note(f"Hit the cap of {MAX_REACT_TURNS} model calls without a final answer.")

    # ---- B. Plan-and-execute ----
    ctx.step("B. Plan-and-execute: one plan, run by code")
    plan_response = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=[{"role": "system", "content": PLANNER_SYSTEM}, {"role": "user", "content": TASK}],
        response_format={"type": "json_object"},
    )
    ctx.record_usage(plan_response.usage, quiet=True)
    plan_calls = 1
    try:
        steps = json.loads(plan_response.choices[0].message.content or "")["steps"]
        steps = [(s["tool"], dict(s["args"])) for s in steps]
    except (ValueError, KeyError, TypeError):
        steps = []
        ctx.note("The planner did not return a usable plan, so nothing runs. Real systems retry or escalate here.")
    ctx.show_data("The plan (inspectable BEFORE anything runs)", [{"tool": n, "args": a} for n, a in steps])

    results = []
    for name, args in steps:
        result = run_step(name, args)
        ctx.show_tool_call(name, args, json.dumps(result))
        results.append({"tool": name, "result": result})

    if results:
        summary = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[
                {"role": "system", "content": "Summarise what was done in one sentence for the on-call engineer."},
                {"role": "user", "content": f"Task: {TASK}\nResults: {json.dumps(results)}"},
            ],
        )
        plan_calls += 1
        ctx.show_response(summary)

    ctx.step("Compare")
    ctx.show_data("Model calls", {"react": react_calls, "plan_and_execute": plan_calls})
    ctx.show_data("Steps actually executed", {"react": react_steps, "plan_and_execute": len(results)})
    if react_steps < len(steps):
        ctx.note("ReAct stopped before finishing every step: the model ended its turn early (sometimes with text instead of a tool call). A plan you can count steps against makes that visible; with ReAct you only notice by checking.")
    ctx.note("ReAct pays one call per step but can adapt; plan-and-execute pays two calls however long the plan is, but it is blind to failures. 13.2/2 adds replanning.")


if __name__ == "__main__":
    main()
