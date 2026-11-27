"""01.3/3  Helpdesk replies: when to be predictable, when to be lively

The running example has two kinds of writing. A policy answer must be the same for every
employee who asks, so it runs at temperature 0. An outage announcement should sound human
and can vary, so it runs at a higher temperature. Each is written twice so you can compare.

Run it:   ./run 01.3/3          (Windows: run 01.3/3)
"""

import openai

from labkit import lesson

SYSTEM_PROMPT = "You are the IT helpdesk assistant at Larkspur Labs. Be plain and friendly."

POLICY_QUESTION = """Policy: passwords expire every 90 days; minimum 14 characters; the last 5 passwords cannot be reused.
Question from an employee: How often do I have to change my password, and can I reuse an old one?
Answer in one sentence, using only the policy."""

ANNOUNCEMENT_REQUEST = """Write a light-hearted two-sentence announcement for the staff chat channel, with a small joke:
the 3rd-floor printers will be offline on Thursday from 13:00 to 14:00 for maintenance."""

TASKS = [
    ("Policy answer: must be consistent", POLICY_QUESTION, 0.0),
    ("Outage announcement: may vary", ANNOUNCEMENT_REQUEST, 1.0),
]


@lesson("01.3/3", "Helpdesk replies: when to be predictable, when to be lively")
def main(ctx):
    summary = {}
    for title, request, temperature in TASKS:
        ctx.step(f"{title} (temperature={temperature})")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request},
        ]
        ctx.show_messages(messages)
        replies = []
        for run in (1, 2):
            try:
                response = ctx.client.chat.completions.create(
                    model=ctx.model,
                    messages=messages,
                    temperature=temperature,
                )
            except openai.BadRequestError:
                ctx.note("This model does not accept a temperature setting; using its default instead.")
                response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
            reply = (response.choices[0].message.content or "").strip()
            ctx.record_usage(response.usage, quiet=True)
            replies.append(reply)
            ctx.note(f"run {run}: {reply}")
        summary[title] = "identical both times" if replies[0] == replies[1] else "different each time"

    ctx.step("Choosing a setting")
    ctx.show_data("Two runs of each task", summary)
    ctx.note("Facts, policies, classification, data extraction: low temperature. You want the same answer twice.")
    ctx.note("Announcements, drafts, brainstorming: higher temperature. Variety is the point.")
    ctx.note("If the announcement came out identical too: temperature allows variety, it does not force it.")


if __name__ == "__main__":
    main()
