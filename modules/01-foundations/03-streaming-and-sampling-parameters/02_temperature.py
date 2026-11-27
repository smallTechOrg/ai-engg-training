"""01.3/2  Temperature and other sampling parameters

A model picks each next word by drawing at random from a list of likely candidates.
`temperature` controls how adventurous that pick is. This script sends the same prompt
several times at a low and a high temperature so you can see the difference. Then it
shows what `stop` does.

Run it:   ./run 01.3/2          (Windows: run 01.3/2)
"""

import openai

from labkit import lesson

PROMPT = "Invent a name for the new coffee machine on the 3rd floor. Reply with the name only."
RUNS_PER_SETTING = 3  # 2 settings x 3 runs = 6 calls
LOW, HIGH = 0.0, 1.0


def ask(ctx, messages, **parameters):
    """One call with extra parameters. Returns the reply text, or None if the provider refused them."""
    try:
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, **parameters)
    except openai.BadRequestError as error:
        # Not every model accepts every parameter (some reasoning models fix the temperature).
        ctx.note(f"The provider rejected {parameters}: {' '.join(str(error).split())[:160]}")
        return None
    ctx.record_usage(response.usage, quiet=True)
    return (response.choices[0].message.content or "").strip()


@lesson("01.3/2", "Temperature and other sampling parameters")
def main(ctx):
    messages = [{"role": "user", "content": PROMPT}]
    ctx.show_messages(messages)
    results = {}

    for temperature in (LOW, HIGH):
        ctx.step(f"The same prompt {RUNS_PER_SETTING} times at temperature={temperature}")
        replies = []
        for run in range(1, RUNS_PER_SETTING + 1):
            reply = ask(ctx, messages, temperature=temperature)
            if reply is None:
                break  # this model does not allow the setting; no point repeating
            replies.append(reply)
            ctx.note(f"  run {run}: {reply}")
        results[temperature] = replies
        if replies:
            ctx.note(f"  -> {len(set(replies))} different answer(s) in {len(replies)} run(s)")

    ctx.step("What that shows")
    ctx.show_data(
        "Distinct answers",
        {f"temperature={t}": f"{len(set(r))} of {len(r)}" if r else "not supported by this model" for t, r in results.items()},
    )
    ctx.note("Low temperature: the model keeps choosing its most likely words, so answers repeat.")
    ctx.note("High temperature: less likely words get a chance, so answers vary (and can get worse).")
    ctx.note("Even at 0 most providers do not promise identical output every time.")

    ctx.step("A different control: stop")
    ctx.note("`stop` ends the reply as soon as the model writes a given text. The text itself is not returned.")
    counting = [{"role": "user", "content": "Count from 1 to 10 in words, separated by commas, on one line."}]
    full = ask(ctx, counting)
    cut = ask(ctx, counting, stop=["six"])
    ctx.note(f"  without stop:      {full}")
    ctx.note(f"  with stop=['six']: {cut}")


if __name__ == "__main__":
    main()
