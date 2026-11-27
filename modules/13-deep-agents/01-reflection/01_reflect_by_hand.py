"""13.1/1  Reflection in plain Python: draft, critique, revise

Reflection means a model reviews its own output against a written standard and then fixes it.
Three calls, no framework:

  1. DRAFT   - write a first version;
  2. CRITIQUE - score it against a rubric (1-5 per criterion) and say what to fix, as JSON;
  3. REVISE  - rewrite the draft using that feedback.

We score the draft and the revision with the same rubric, so you can see whether the loop helped.

Run it:   ./run 13.1/1          (Windows: run 13.1/1)
"""

import json

from labkit import lesson

TASK = "Write a 3-sentence reply to an employee whose laptop battery drains in under an hour."

RUBRIC = {
    "clarity": "A non-technical reader understands every sentence.",
    "actionability": "It gives at least one concrete step the employee can take now.",
    "tone": "Friendly and professional, no blame, no jargon.",
}

CRITIC_SYSTEM = (
    "You are a harsh reviewer. Score from 1 (poor) to 5 (excellent) on each criterion; 5 is rare and a first draft usually earns 2 or 3. "
    "and give one sentence of feedback. Reply with JSON only, shaped like this example: "
    '{"clarity": 3, "actionability": 3, "tone": 3, "feedback": "one sentence"}\n'
    "Criteria:\n" + "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
)


def parse_scores(text: str):
    """Return (scores dict, feedback) or (None, reason) if the model's JSON is unusable."""
    try:
        data = json.loads(text)
        scores = {k: int(data[k]) for k in RUBRIC}
        return scores, str(data.get("feedback", ""))
    except (ValueError, KeyError, TypeError) as exc:
        return None, f"could not read the critique ({type(exc).__name__})"


@lesson("13.1/1", "Reflection in plain Python")
def main(ctx):
    def chat(messages, json_mode=False):
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, **kwargs)
        ctx.record_usage(response.usage, quiet=True)
        return response.choices[0].message.content or ""

    def critique(text):
        reply = chat(
            [{"role": "system", "content": CRITIC_SYSTEM}, {"role": "user", "content": text}],
            json_mode=True,
        )
        return parse_scores(reply)

    ctx.step("Draft")
    draft = chat([{"role": "user", "content": TASK}])
    ctx.note(draft)

    ctx.step("Critique the draft against the rubric")
    ctx.note("The critic is a second call with a different system message: the rubric, and 'reply with JSON'.")
    before, feedback = critique(draft)
    ctx.show_data("Scores and feedback", {"scores": before, "feedback": feedback})

    ctx.step("Revise using the feedback")
    revised = chat(
        [
            {"role": "system", "content": "Improve the text. Keep it to 3 sentences. Return only the improved text."},
            {"role": "user", "content": f"Task: {TASK}\n\nDraft:\n{draft}\n\nReviewer feedback: {feedback}"},
        ]
    )
    ctx.note(revised)

    ctx.step("Score the revision with the same rubric")
    after, feedback2 = critique(revised)
    if before and after:
        rows = {k: f"{before[k]} -> {after[k]}" for k in RUBRIC}
        ctx.show_data("Scores before -> after", rows)
        ctx.note(f"Average: {sum(before.values()) / len(before):.1f} -> {sum(after.values()) / len(after):.1f}")
    else:
        ctx.note("The critic did not return usable JSON, so there is nothing to compare. That happens; see the README.")
    ctx.note("One round, no loop. 13.1/2 turns this into a loop that stops when the score is high enough.")


if __name__ == "__main__":
    main()
