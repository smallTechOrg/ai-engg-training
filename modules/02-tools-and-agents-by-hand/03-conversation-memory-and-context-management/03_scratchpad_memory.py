"""02.3/3  A scratchpad: pin the facts that must never be summarised away

New since script 2: a summary is lossy, so important facts get their own place. After each user
turn the program asks the model to pull out "facts worth keeping" as JSON (asset tag, username,
ticket id, preferred day...) and merges them into a `scratchpad` dict. The scratchpad is pinned
into the system prompt on every call, while the chat history itself can stay a short window.

Pattern: window for the flow of talk, scratchpad for the facts. The scratchpad is plain Python
state: you can print it, test it, and correct it.

Run it:   ./run 02.3/3          (Windows: run 02.3/3)
"""

import json

from labkit import lesson

WINDOW = 2  # messages of chat history kept verbatim
BASE_SYSTEM = "You are the Larkspur Labs IT helpdesk assistant. Answer in one short sentence."
USER_TURNS = [
    "Hi, I am dmorgan, my laptop asset tag is LL-L-0412 and it will not charge.",
    "I tried a second charger, the light stays off.",
    "It shuts down after a minute on mains power.",
    "Please book the hardware check for Thursday, I am only in the Leeds office that day.",
]
QUESTION = "Remind me what you have on file for me: username, asset tag and the day I can be in?"

EXTRACT_PROMPT = (
    "Extract durable facts from the user's message as a JSON object. Allowed keys: username, asset_tag, "
    "ticket_id, office, available_day. Include only keys that the message states. Reply with JSON only."
)


def extract_facts(ctx, text):
    """One small model call that returns {} when the reply is not usable."""
    response = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=[{"role": "system", "content": EXTRACT_PROMPT}, {"role": "user", "content": text}],
        response_format={"type": "json_object"},
    )
    ctx.record_usage(response.usage, quiet=True)
    try:
        data = json.loads(response.choices[0].message.content or "{}")
    except ValueError:
        return {}
    allowed = {"username", "asset_tag", "ticket_id", "office", "available_day"}
    # Keep only allowed keys with simple string values: the model's JSON is untrusted input.
    return {k: v for k, v in data.items() if k in allowed and isinstance(v, str)} if isinstance(data, dict) else {}


@lesson("02.3/3", "A scratchpad: pin the facts that must never be forgotten")
def main(ctx):
    scratchpad, history = {}, []
    ctx.step("Process the conversation: extract facts, keep a short window")
    # Only two extraction calls are shown, to keep the run short. The other turns are added without extraction.
    for index, turn in enumerate(USER_TURNS, start=1):
        history += [{"role": "user", "content": turn}, {"role": "assistant", "content": "Noted."}]
        if index in (1, 4):
            facts = extract_facts(ctx, turn)
            scratchpad.update(facts)
            ctx.note(f"Turn {index}: extracted {facts or 'nothing'}")
    ctx.show_data("Scratchpad after the conversation", scratchpad)

    ctx.step("Build the context: pinned facts + a window of only the last messages")
    pinned = BASE_SYSTEM + "\nFacts on file (trust these):\n" + json.dumps(scratchpad, indent=2)
    messages = [{"role": "system", "content": pinned}] + history[-WINDOW:] + [{"role": "user", "content": QUESTION}]
    ctx.show_messages(messages)
    ctx.note(f"The window holds {WINDOW} of {len(history)} history messages. The asset tag is long gone from it, but it is in the scratchpad.")

    ctx.step("Ask")
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    ctx.show_response(response)
    answer = response.choices[0].message.content or ""
    for key in ("asset_tag", "username", "available_day"):
        value = scratchpad.get(key)
        if value:
            ctx.note(f"  {key} = {value!r}: {'in the answer' if value.lower() in answer.lower() or value.lower().split()[-1] in answer.lower() else 'NOT in the answer'}")
    ctx.note("Extraction is a model call too, so it can miss a fact. Show the scratchpad to the user and let them correct it.")


if __name__ == "__main__":
    main()
