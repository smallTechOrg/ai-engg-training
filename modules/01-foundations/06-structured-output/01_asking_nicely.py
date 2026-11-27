"""01.6/1  Asking nicely for JSON

The obvious first attempt: say "reply with JSON" in the prompt and parse whatever comes back.
It works often enough to be tempting and fails often enough to be dangerous.

This script asks once, then tries to read the reply two ways:
  1. json.loads() on the raw text;
  2. a defensive parser that strips code fences and surrounding chatter.

Run it:   ./run 01.6/1          (Windows: run 01.6/1)
"""

import json
import re

from labkit import lesson

TICKET = """Ticket #5127 from Omar (Sales):
Since the update last night the CRM app closes itself as soon as I open a customer record.
I have a demo with a customer at 2pm and I can't look anything up."""

PROMPT = f"""Extract these fields from the helpdesk ticket and reply with JSON:
- category: network, hardware, software or access
- urgency: low, medium or high
- summary: one sentence
- needs_human: true or false

{TICKET}"""

EXPECTED_KEYS = ["category", "urgency", "summary", "needs_human"]


def parse_defensively(text):
    """Dig a JSON object out of a chatty reply. Returns (data or None, what was done)."""
    notes = []
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
        notes.append("removed a ``` code fence")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None, notes + ["found no {...} in the reply"]
    if text[:start].strip() or text[end + 1 :].strip():
        notes.append("dropped text before or after the object")
    try:
        data = json.loads(text[start : end + 1])
    except ValueError as error:
        return None, notes + [f"the text between the braces is not valid JSON ({error})"]
    if not isinstance(data, dict):
        return None, notes + ["parsed, but it is not a JSON object"]
    return data, notes or ["nothing to clean up"]


@lesson("01.6/1", "Asking nicely for JSON")
def main(ctx):
    ctx.step("Ask for JSON in ordinary text mode")
    messages = [{"role": "user", "content": PROMPT}]
    ctx.show_messages(messages)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    reply = ctx.show_response(response)

    ctx.step("Attempt 1: json.loads() on the raw reply")
    try:
        json.loads(reply)
        ctx.note("It parsed. This time. Nothing in the request guaranteed it.")
    except ValueError as error:
        ctx.note(f"Failed: {error}")
        ctx.note("The model wrapped the JSON in something (a code fence, a sentence), or did not write JSON at all.")

    ctx.step("Attempt 2: a defensive parser")
    data, notes = parse_defensively(reply)
    ctx.note("What the parser had to do: " + "; ".join(notes) + ".")
    if data is None:
        ctx.note("No usable object. A program depending on this reply would have to stop or retry here.")
    else:
        ctx.show_data("Recovered object", data)
        missing = [key for key in EXPECTED_KEYS if key not in data]
        extra = [key for key in data if key not in EXPECTED_KEYS]
        ctx.note(f"Keys missing: {missing or 'none'}. Unexpected keys: {extra or 'none'}.")
        ctx.note(f"Type of needs_human: {type(data.get('needs_human')).__name__} (we wanted bool).")

    ctx.step("Why this is fragile")
    ctx.note("Every line of that parser is a guess about how the model will misbehave next time.")
    ctx.note("Nothing checked the values either: 'urgency' could be 'ASAP' and this code would accept it.")
    ctx.note("The next two scripts move both jobs to where they belong: the API guarantees the syntax, a schema checks the content.")


if __name__ == "__main__":
    main()
