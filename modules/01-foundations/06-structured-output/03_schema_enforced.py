"""01.6/3  Schema-enforced output

The strongest form: hand the API the JSON schema itself. With "strict": True the provider
constrains the model while it writes, so the reply cannot have a missing key, an extra key
or a value outside an enum.

The schema is generated from the same pydantic model that validates the reply, so there is
one definition of the shape, not two.

Not every provider or model supports this. When the endpoint refuses, the script explains
and falls back to JSON mode from the previous script.

Run it:   ./run 01.6/3          (Windows: run 01.6/3)
"""

import json
from typing import Literal

import openai
from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson


class Triage(BaseModel):
    # Strict mode requires every property to be required and no extra keys allowed.
    # extra="forbid" puts "additionalProperties": false into the generated schema.
    model_config = ConfigDict(extra="forbid")

    category: Literal["network", "hardware", "software", "access"]
    urgency: Literal["low", "medium", "high"]
    summary: str
    needs_human: bool


SYSTEM_PROMPT = """You triage IT helpdesk tickets for Larkspur Labs.
summary is one sentence.
needs_human is true when a person must act (a visit, a replacement, an approval)."""

# Used only by the fallback: JSON mode needs to be shown the shape.
SHAPE_HINT = """
Reply with a JSON object in exactly this shape:
{"category": "access", "urgency": "low", "summary": "One sentence describing the problem.", "needs_human": false}
category is one of: network, hardware, software, access. urgency is one of: low, medium, high."""

TICKET = """Ticket #5130 from Mei (Reception):
The badge reader at the front door has been dead since the power cut. Visitors are waiting
outside and I have to let each one in by hand."""


@lesson("01.6/3", "Schema-enforced output")
def main(ctx):
    ctx.step("Generate the schema from the pydantic model")
    schema = Triage.model_json_schema()
    ctx.show_data("Triage.model_json_schema()", schema)

    ctx.step("Ask with the schema attached")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TICKET},
    ]
    ctx.note("Notice the prompt no longer describes the JSON shape: the schema does that job.")
    ctx.show_messages(messages)
    try:
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "triage", "schema": schema, "strict": True},
            },
        )
        mode = "json_schema (strict)"
    except (openai.BadRequestError, openai.UnprocessableEntityError) as error:
        ctx.note("The endpoint refused the schema request. This model or provider does not support json_schema.")
        ctx.note("Provider said: " + " ".join(str(error).split())[:200])
        ctx.step("Fall back to JSON mode")
        messages[0] = {"role": "system", "content": SYSTEM_PROMPT + SHAPE_HINT}
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=messages,
            response_format={"type": "json_object"},
        )
        mode = "json_object (fallback)"
    reply = ctx.show_response(response)

    ctx.step("Validate anyway")
    ctx.note(f"Mode used: {mode}. We still validate: a fallback, a refusal or a cut-off reply can all break the shape.")
    try:
        triage = Triage.model_validate_json(reply)
    except ValidationError as error:
        ctx.note(f"REJECTED, {error.error_count()} problem(s):")
        for problem in error.errors():
            where = ".".join(str(part) for part in problem["loc"]) or "(whole reply)"
            ctx.note(f"  - {where}: {problem['msg']}")
        ctx.note("In a real system this is where you would retry once or route the ticket to a person.")
        return
    ctx.show_data("Validated triage", triage)

    ctx.step("Use it like any other data")
    queue = "on-site support" if triage.needs_human else "self-service reply"
    ctx.note(f"Routing decision made by ordinary code: {triage.category} / {triage.urgency} -> {queue}")
    ctx.note("As a dict for a database or an API: " + json.dumps(triage.model_dump()))


if __name__ == "__main__":
    main()
