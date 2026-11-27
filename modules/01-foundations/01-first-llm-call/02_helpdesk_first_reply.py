"""01.1/2  The helpdesk assistant's first reply

The same call as before, used for this course's running example: an IT helpdesk
assistant. Two things are new:

  1. a `system` message, which tells the model what job it is doing
  2. streaming, so the reply appears piece by piece instead of all at once

Run it:   ./run 01.1/2          (Windows: run 01.1/2)
"""

from labkit import lesson

SYSTEM_PROMPT = """You are the first-line IT helpdesk assistant at Larkspur Labs.
Reply to the employee in at most four short sentences.
Give one concrete thing to try first. If it might not work, say what you will do next.
Be friendly and plain; no jargon."""

TICKET = """Ticket #4821 from Priya (Finance):
My laptop won't connect to the office Wi-Fi since this morning. Other people near me are
fine. I have a client call in 20 minutes."""


@lesson("01.1/2", "The helpdesk assistant's first reply")
def main(ctx):
    ctx.step("Give the model a job with a system message")
    ctx.note("The system message sets the role and the rules. The user message is the ticket.")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TICKET},
    ]
    ctx.show_messages(messages)

    ctx.step("Ask for the reply as a stream")
    ctx.note("stream=True makes the model send its answer in small pieces as it writes them.")
    stream = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},  # ask for token counts at the end of the stream
    )
    reply = ctx.show_stream(stream)

    ctx.step("What we have now")
    ctx.note(f"The full reply is an ordinary string of {len(reply)} characters, ready to send to Priya.")
    ctx.note("Nothing here is specific to helpdesks: change SYSTEM_PROMPT and you have a different assistant.")


if __name__ == "__main__":
    main()
