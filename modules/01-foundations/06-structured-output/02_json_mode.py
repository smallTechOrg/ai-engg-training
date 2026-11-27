"""01.6/2  JSON mode, validated with pydantic

Two improvements on "asking nicely":

  1. response_format={"type": "json_object"} makes the API return syntactically valid
     JSON: no code fences, no chatter. It does NOT promise the right keys or values.
  2. A pydantic model checks keys, types and allowed values, and tells you exactly what
     is wrong when the reply does not fit.

JSON mode knows nothing about your shape, so the prompt must show it.

Run it:   ./run 01.6/2          (Windows: run 01.6/2)
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson


class Triage(BaseModel):
    """The shape we want back. This class is the single definition of 'a valid reply'."""

    model_config = ConfigDict(extra="forbid")  # unknown keys are an error, not a surprise

    category: Literal["network", "hardware", "software", "access"]
    urgency: Literal["low", "medium", "high"]
    summary: str
    needs_human: bool


SYSTEM_PROMPT = """You triage IT helpdesk tickets for Larkspur Labs.
Reply with a JSON object in exactly this shape:
{"category": "access", "urgency": "low", "summary": "One sentence describing the problem.", "needs_human": false}

category is one of: network, hardware, software, access.
urgency is one of: low, medium, high.
needs_human is true when a person must act (a visit, a replacement, an approval)."""

TICKET = """Ticket #5127 from Omar (Sales):
Since the update last night the CRM app closes itself as soon as I open a customer record.
I have a demo with a customer at 2pm and I can't look anything up."""

# A reply that is perfectly valid JSON and still wrong, to show what validation catches.
BROKEN_REPLY = '{"category": "crm", "urgency": 5, "summary": "CRM crashes.", "priority": "P1"}'


def explain(error: ValidationError) -> list[str]:
    """Turn pydantic's error list into one plain line per problem."""
    lines = []
    for problem in error.errors():
        where = ".".join(str(part) for part in problem["loc"]) or "(whole reply)"
        lines.append(f"{where}: {problem['msg']}")
    return lines


def validate(ctx, label, reply):
    try:
        triage = Triage.model_validate_json(reply)
    except ValidationError as error:
        ctx.note(f"{label}: REJECTED, {error.error_count()} problem(s):")
        for line in explain(error):
            ctx.note(f"  - {line}")
        return None
    ctx.note(f"{label}: valid.")
    return triage


@lesson("01.6/2", "JSON mode, validated with pydantic")
def main(ctx):
    ctx.step("Ask in JSON mode, with the shape shown in the prompt")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TICKET},
    ]
    ctx.show_messages(messages)
    response = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=messages,
        response_format={"type": "json_object"},  # the reply will be parseable JSON
    )
    reply = ctx.show_response(response)

    ctx.step("Validate the reply against the Triage model")
    triage = validate(ctx, "Model reply", reply)
    if triage is not None:
        ctx.show_data("A typed Python object", triage)
        ctx.note(f"Code can now branch on real values: needs_human is the bool {triage.needs_human}, urgency is '{triage.urgency}'.")

    ctx.step("What validation catches (no model call)")
    ctx.note("This reply is valid JSON, so JSON mode would have let it through:")
    ctx.console.print(BROKEN_REPLY, markup=False)
    validate(ctx, "Broken reply", BROKEN_REPLY)
    ctx.note("JSON mode guarantees syntax. Only the schema check guarantees meaning.")


if __name__ == "__main__":
    main()
