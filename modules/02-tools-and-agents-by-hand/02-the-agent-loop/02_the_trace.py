"""02.2/2  Make the loop inspectable: a step trace and named stop reasons

New since script 1: the loop becomes a function that returns a RESULT, not just printed output.
Every turn is recorded as a `Step` (what the model said, which tools ran, how long it took),
and the run ends with one named stop reason: `answered`, `step_cap` or `empty_reply`.

A trace like this is what you read when an agent misbehaves, and what you assert on in tests.

Run it:   ./run 02.2/2          (Windows: run 02.2/2)
"""

import json
import time
from dataclasses import dataclass, field

from labkit import lesson

MAX_STEPS = 6

TICKETS = {
    "LL-2062": {"from": "mchen", "subject": "Shared drive is read-only", "status": "open"},
    "LL-2063": {"from": "tsato", "subject": "New starter needs a laptop", "status": "in progress"},
}


def lookup_ticket(ticket_id: str) -> dict:
    ticket = TICKETS.get(ticket_id.strip().upper())
    return {"ticket_id": ticket_id, **ticket} if ticket else {"error": f"No ticket {ticket_id!r}."}


FUNCTIONS = {"lookup_ticket": lookup_ticket}
TOOLS = [{"type": "function", "function": {
    "name": "lookup_ticket", "description": "Read a helpdesk ticket by id.",
    "parameters": {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]}}}]


@dataclass
class Step:
    number: int
    seconds: float
    said: str
    actions: list = field(default_factory=list)  # (tool, arguments, result)


@dataclass
class AgentResult:
    stop_reason: str
    answer: str
    steps: list


def run_agent(ctx, messages, max_steps=MAX_STEPS) -> AgentResult:
    """The loop from script 1, returning a structured result instead of printing as it goes."""
    steps = []
    for number in range(1, max_steps + 1):
        started = time.perf_counter()
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=TOOLS)
        ctx.record_usage(response.usage, quiet=True)
        message = response.choices[0].message
        step = Step(number, time.perf_counter() - started, (message.content or "").strip())
        steps.append(step)
        if not message.tool_calls:
            return AgentResult("answered" if step.said else "empty_reply", step.said, steps)
        messages.append({
            "role": "assistant", "content": message.content,
            "tool_calls": [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in message.tool_calls],
        })
        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
                result = FUNCTIONS[call.function.name](**args)
            except (ValueError, TypeError, KeyError) as error:
                args, result = call.function.arguments, {"error": f"Could not run the tool: {error!r}"}
            step.actions.append((call.function.name, args, result))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    return AgentResult("step_cap", "", steps)


@lesson("02.2/2", "Make the loop inspectable: a step trace")
def main(ctx):
    ctx.step("Run the agent on a two-ticket question")
    messages = [
        {"role": "system", "content": "You are the Larkspur Labs helpdesk agent. Use lookup_ticket for every ticket id the user mentions, then summarise each in one line."},
        {"role": "user", "content": "Summarise tickets LL-2062 and LL-2063, and say which one is still open."},
    ]
    result = run_agent(ctx, messages)

    ctx.step("The trace")
    for step in result.steps:
        ctx.note(f"step {step.number}: {step.seconds:.1f}s, {len(step.actions)} tool call(s), text: {step.said[:70] or '(none)'}")
        for tool, args, outcome in step.actions:
            ctx.show_tool_call(tool, args, json.dumps(outcome))

    ctx.step("The stop reason")
    ctx.note(f"stop_reason = {result.stop_reason!r} after {len(result.steps)} step(s)")
    if result.answer:
        ctx.console.print(result.answer, markup=False)

    ctx.step("Force the cap to see a second stop reason")
    ctx.note("Same task with max_steps=1: one model call cannot both ask for tools and answer.")
    capped = run_agent(ctx, [dict(m) for m in messages[:2]], max_steps=1)
    ctx.note(f"stop_reason = {capped.stop_reason!r}. The caller can now decide: retry with a higher cap, or hand over to a person.")
    ctx.note("Because the result is data, a test can assert on it: assert result.stop_reason == 'answered'.")


if __name__ == "__main__":
    main()
