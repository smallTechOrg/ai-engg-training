"""10.3/1  LLM-as-judge: a model scores replies against a rubric

Heuristics (10.2) cannot tell whether a reply is helpful, honest or polite. A second model
call can: you give it a rubric and the reply, and it returns scores. The rubric is the
important part. A vague "rate this 1-10" is noisy; three specific 1-5 questions are usable.

Here the judge scores three hand-written replies to the same ticket, one good and two flawed
on purpose, so we can check whether the judge notices. Then we ask it again to see how stable it is.

Run it:   ./run 10.3/1          (Windows: run 10.3/1)
"""

import json

from labkit import lesson

TICKET = "My laptop battery looks swollen and the trackpad is lifting off the case."

REPLIES = {
    "R1 good": "A swollen battery can be a fire risk. Please shut the laptop down, unplug it and do not charge it. Bring it to the IT desk today and we will arrange a replacement.",
    "R2 invents an action": "Thanks for letting us know! I have already ordered you a new laptop and it will arrive tomorrow. No need to do anything.",
    "R3 curt": "Not our problem, laptops wear out. Buy a new one.",
}

JUDGE_PROMPT = """You are a strict reviewer of IT helpdesk replies at Larkspur Labs. You receive one ticket and several candidate replies.
Score every reply on three criteria, each an integer from 1 (very poor) to 5 (excellent):
- no_invented_actions: 5 = the reply promises or claims only things a chat assistant could really do; 1 = it claims it already did something (ordered, reset, dispatched) that an assistant cannot do.
- actionable: 5 = the employee knows exactly what to do next; 1 = no next step.
- tone: 5 = polite and calm; 1 = rude or dismissive.
Reply with only JSON: {"scores": [{"id": "R0", "no_invented_actions": 1, "actionable": 1, "tone": 1, "reason": "one short sentence"}]}
One entry per reply, ids copied exactly."""


def ask_judge(ctx, label):
    body = f"<ticket>\n{TICKET}\n</ticket>\n\n" + "\n\n".join(
        f'<reply id="{rid.split()[0]}">\n{text}\n</reply>' for rid, text in REPLIES.items()
    )
    messages = [{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": body}]
    response = ctx.client.chat.completions.create(
        model=ctx.model, messages=messages, response_format={"type": "json_object"}, temperature=0
    )
    ctx.record_usage(response.usage, quiet=True)
    raw = response.choices[0].message.content or ""
    try:
        return {s["id"]: s for s in json.loads(raw)["scores"]}, raw
    except (ValueError, KeyError, TypeError):
        return {}, raw


@lesson("10.3/1", "LLM-as-judge with a three-question rubric")
def main(ctx):
    ctx.step("1. The ticket and three candidate replies")
    ctx.note(TICKET)
    for rid, text in REPLIES.items():
        ctx.note(f"{rid}: {text}")

    ctx.step("2. The rubric is the prompt: three specific 1-5 questions")
    ctx.note(JUDGE_PROMPT)

    ctx.step("3. Ask the judge (temperature 0, JSON mode)")
    first, raw = ask_judge(ctx, "first")
    if not first:
        ctx.note("The judge did not return the expected JSON. In a real suite that row counts as 'not judged', never as a pass. Raw reply:")
        ctx.note(raw[:300])
    criteria = ["no_invented_actions", "actionable", "tone"]
    ctx.note(f"{'reply':22}" + "".join(f"{c:>21}" for c in criteria))
    for rid in REPLIES:
        s = first.get(rid.split()[0], {})
        ctx.note(f"{rid:22}" + "".join(f"{str(s.get(c, '-')):>21}" for c in criteria))
    for rid in REPLIES:
        reason = first.get(rid.split()[0], {}).get("reason")
        if reason:
            ctx.note(f"{rid}: {reason}")

    ctx.step("4. Is the judge stable? Ask again with the identical input")
    second, _ = ask_judge(ctx, "second")
    same = sum(
        1 for rid in REPLIES for c in criteria
        if first.get(rid.split()[0], {}).get(c) is not None and first[rid.split()[0]].get(c) == second.get(rid.split()[0], {}).get(c)
    )
    ctx.note(f"{same} of {len(REPLIES) * len(criteria)} scores identical between the two runs.")

    ctx.step("What to notice")
    ctx.note("A judge is a model: it can be wrong, lenient or inconsistent. Use specific questions, integer scales and temperature 0.")
    ctx.note("Before trusting a judge, run it on replies you KNOW are bad (as here). If it cannot fail them, it cannot catch regressions.")
    ctx.note("The judge here is the same model as the assistant; judges tend to favour their own style. A different, stronger model is better when you have one.")


if __name__ == "__main__":
    main()
