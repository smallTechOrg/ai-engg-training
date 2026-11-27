"""13.2/3  Scenario: a validated plan for a phishing report

A user says they typed their password into a phishing page. The assistant plans a containment,
but a plan from a model is untrusted input, so it passes a gate BEFORE anything runs:

  - every tool must exist and have its required arguments (pydantic checks the shape);
  - at most MAX_STEPS steps;
  - tools marked risky are listed for approval (here approved automatically and printed; a real
    system would ask a person - see module 09 for human-in-the-loop).

An invalid plan goes back to the planner once with the errors. A step that fails triggers a replan
(capped), exactly as in 13.2/2. The simulated identity provider times out on its first
revoke_sessions call, so a replan or retry is expected.

Run it:   ./run 13.2/3          (Windows: run 13.2/3)
"""

import json

from pydantic import BaseModel, ValidationError

from labkit import lesson

MAX_STEPS = 8
MAX_PLAN_ATTEMPTS = 2
MAX_REPLANS = 2

REPORT = (
    "Dana Morgan (username dmorgan) says she typed her Larkspur Labs password into a fake "
    "'mailbox full' page twenty minutes ago. Contain this and tell her manager."
)

# tool -> (description, required args, risky?)
TOOL_SPECS = {
    "lookup_user": ("Read a user's profile and manager.", ["username"], False),
    "revoke_sessions": ("Sign the user out everywhere.", ["username"], True),
    "reset_password": ("Force a password reset.", ["username"], True),
    "notify_manager": ("Message the user's manager.", ["username", "message"], False),
    "open_security_ticket": ("Open a ticket for the security team.", ["username", "summary"], False),
}

state = {"revoke_calls": 0}


def lookup_user(username):
    return {"ok": True, "username": username, "manager": "Sam Okoye"}


def revoke_sessions(username):
    state["revoke_calls"] += 1
    if state["revoke_calls"] == 1:
        return {"ok": False, "error": "identity provider timed out"}
    return {"ok": True, "revoked": username}


def reset_password(username):
    return {"ok": True, "reset_link_sent": username}


def notify_manager(username, message):
    return {"ok": True, "notified": "manager of " + username}


def open_security_ticket(username, summary):
    return {"ok": True, "ticket": "SEC-114"}


FUNCTIONS = {f.__name__: f for f in (lookup_user, revoke_sessions, reset_password, notify_manager, open_security_ticket)}


class Step(BaseModel):
    tool: str
    args: dict


class Plan(BaseModel):
    steps: list[Step]


# The FIRST JSON object in the prompt is a format example for a different (invented) situation.
PLANNER_SYSTEM = (
    'Write a containment plan as JSON only, shaped like this example: {"steps": [{"tool": "lookup_user", "args": {"username": "alexample"}}, '
    '{"tool": "open_security_ticket", "args": {"username": "alexample", "summary": "one line"}}]}\n'
    "Tools and their required arguments:\n"
    + "\n".join(f"- {n}({', '.join(req)}): {d}" for n, (d, req, _) in TOOL_SPECS.items())
    + f"\nAt most {MAX_STEPS} steps, in the order they must run. Return {{\"steps\": []}} if nothing is left to do."
)


def validate(plan: Plan) -> list[str]:
    """Return a list of problems; empty means the plan may run."""
    problems = []
    if len(plan.steps) > MAX_STEPS:
        problems.append(f"too many steps ({len(plan.steps)} > {MAX_STEPS})")
    for i, step in enumerate(plan.steps, 1):
        spec = TOOL_SPECS.get(step.tool)
        if spec is None:
            problems.append(f"step {i}: unknown tool {step.tool!r}")
            continue
        missing = [a for a in spec[1] if a not in step.args]
        if missing:
            problems.append(f"step {i}: {step.tool} is missing {missing}")
    return problems


@lesson("13.2/3", "Scenario: a validated containment plan")
def main(ctx):
    def get_plan(user_text: str):
        """Ask for a plan; on problems, one retry with the errors. Returns (Plan or None, problems)."""
        messages = [{"role": "system", "content": PLANNER_SYSTEM}, {"role": "user", "content": user_text}]
        problems: list[str] = []
        for attempt in range(1, MAX_PLAN_ATTEMPTS + 1):
            response = ctx.client.chat.completions.create(
                model=ctx.model, messages=messages, response_format={"type": "json_object"}
            )
            ctx.record_usage(response.usage, quiet=True)
            text = response.choices[0].message.content or ""
            try:
                plan = Plan.model_validate_json(text)
                problems = validate(plan)
            except ValidationError as exc:
                plan, problems = None, [f"not a valid plan object ({exc.error_count()} error(s))"]
            if plan is not None and not problems:
                return plan, []
            ctx.note(f"Plan attempt {attempt} rejected by the gate: {problems}")
            messages += [{"role": "assistant", "content": text}, {"role": "user", "content": f"Fix these problems and return the plan again: {problems}"}]
        return None, problems

    ctx.step("The report")
    ctx.note(REPORT)

    ctx.step("Plan, then pass the gate")
    plan, problems = get_plan(REPORT)
    if plan is None:
        ctx.note(f"No valid plan after {MAX_PLAN_ATTEMPTS} attempts ({problems}). Escalate to the on-call engineer; nothing was run.")
        return
    ctx.show_data("Plan 1", [s.model_dump() for s in plan.steps])
    risky = [s.tool for s in plan.steps if TOOL_SPECS[s.tool][2]]
    ctx.note(f"Risky steps needing approval: {risky or 'none'}. (Auto-approved in this lesson; a real system asks a person.)")

    ctx.step("Execute with replanning")
    queue = list(plan.steps)
    done: list[str] = []
    replans = 0
    outcome = "all steps done"
    while queue:
        step = queue.pop(0)
        result = FUNCTIONS[step.tool](**{k: step.args[k] for k in TOOL_SPECS[step.tool][1]})
        ctx.show_tool_call(step.tool, step.args, json.dumps(result))
        if result.get("ok"):
            done.append(step.tool)
            continue
        if replans >= MAX_REPLANS:
            outcome = f"stopped: {step.tool} failed and the replan cap ({MAX_REPLANS}) is spent -> escalate to a human"
            break
        replans += 1
        ctx.note(f"{step.tool} failed ({result['error']}). Replan {replans} of {MAX_REPLANS}.")
        new_plan, problems = get_plan(
            f"Situation: {REPORT}\nAlready done: {done}\nFailed: {step.model_dump_json()} with error {result['error']!r}.\n"
            "Plan ONLY the remaining work. Retrying a failed step is allowed once if the error looks temporary."
        )
        if new_plan is None:
            outcome = "stopped: no valid replan -> escalate to a human"
            break
        queue = list(new_plan.steps)
        ctx.show_data(f"Plan {replans + 1}", [s.model_dump() for s in queue])

    ctx.step("Outcome")
    ctx.show_data("Completed steps", done)
    ctx.note(f"Outcome: {outcome}. Replans used: {replans} of {MAX_REPLANS}.")


if __name__ == "__main__":
    main()
