"""01.2/2  A conversation loop

Every chat application runs this loop: add the user's message to a list, send the whole
list, add the model's reply, and repeat. Watch the list grow, and the prompt tokens with it.

Run it:   ./run 01.2/2          (Windows: run 01.2/2)
Chat with it yourself:   ./run 01.2/2 --chat     (type your own messages; empty line to stop)
"""

import sys

from labkit import lesson

SCRIPTED_TURNS = [
    "I'm planning a team lunch for 8 people next Friday. Suggest one type of cuisine, in one sentence.",
    "Two of us are vegetarian. Does your suggestion still work? One sentence.",
    "Good. Remind me: how many people, and which day? One sentence.",
]
MAX_TURNS = 6  # hard cap, also for --chat


def user_turns():
    """Yield the user's messages: scripted by default, typed when --chat is given in a terminal."""
    if "--chat" in sys.argv and sys.stdin.isatty():
        for _ in range(MAX_TURNS):
            try:
                text = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                return
            if not text:
                return
            yield text
    else:
        yield from SCRIPTED_TURNS[:MAX_TURNS]


@lesson("01.2/2", "A conversation loop")
def main(ctx):
    ctx.step("Start with a system message")
    messages = [{"role": "system", "content": "You are a concise, practical assistant."}]
    ctx.show_messages(messages, label="The conversation so far")
    prompt_tokens_per_turn = []

    for number, text in enumerate(user_turns(), 1):
        ctx.step(f"Turn {number}: append the user message, send everything")
        messages.append({"role": "user", "content": text})
        ctx.show_messages(messages, label=f"Messages sent to the model ({len(messages)} messages)")

        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        reply = ctx.show_response(response)

        # The step that creates "memory": keep the reply so the next call includes it.
        messages.append({"role": "assistant", "content": reply})
        prompt_tokens_per_turn.append(response.usage.prompt_tokens if response.usage else None)

    ctx.step("What grew")
    ctx.note(f"The list now holds {len(messages)} messages. Prompt tokens sent on each turn:")
    for number, count in enumerate(prompt_tokens_per_turn, 1):
        ctx.note(f"  turn {number}: {count if count is not None else 'not reported by this endpoint'}")
    ctx.note("Each turn resends all earlier turns, so every turn costs more than the one before.")


if __name__ == "__main__":
    main()
