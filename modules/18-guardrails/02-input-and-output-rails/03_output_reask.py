"""18.2/3  Output validation with re-ask

Guardrails AI's signature move: validate the model's reply, and if it fails, ask again with
the failure reason appended (on_fail="reask", num_reasks=N). Here the policy is a house style
for replies: at most 40 words, and it must name a next step. The loop has a hard cap.

Run it:   ./run 18.2/3          (Windows: run 18.2/3)
     or:  python modules/18-guardrails/02-input-and-output-rails/03_output_reask.py
"""

import re

from labkit import lesson

# ---- a tiny Guard/validator engine (the shape Guardrails AI and NeMo input/output rails share) ----
class ValidationError(Exception):
    pass


class Result:
    """What a validator returns: passed or not, why, and (for on_fail="fix") a repaired value."""

    def __init__(self, ok, reason="", fixed=None):
        self.ok, self.reason, self.fixed = ok, reason, fixed


class Validator:
    name = "validator"

    def __init__(self, on_fail="exception"):
        assert on_fail in ("exception", "fix", "filter", "noop", "reask")
        self.on_fail = on_fail

    def validate(self, value):
        raise NotImplementedError


class Outcome:
    def __init__(self, value):
        self.passed, self.value, self.log, self.reask, self.reasons = True, value, [], False, []


class Guard:
    """Runs validators in order. Each failure is handled by that validator's on_fail policy."""

    def __init__(self, name):
        self.name, self.validators = name, []

    def use(self, validator):
        self.validators.append(validator)
        return self

    def validate(self, value):
        out = Outcome(value)
        for v in self.validators:
            res = v.validate(out.value)
            if res.ok:
                out.log.append(f"{v.name}: pass")
                continue
            out.log.append(f"{v.name}: FAIL ({res.reason}) -> {v.on_fail}")
            out.reasons.append(f"{v.name}: {res.reason}")
            if v.on_fail == "exception":
                raise ValidationError(f"{self.name}/{v.name}: {res.reason}")
            if v.on_fail == "fix" and res.fixed is not None:
                out.value = res.fixed
            elif v.on_fail == "filter":
                out.passed, out.value = False, None
                return out
            elif v.on_fail == "reask":
                out.passed, out.reask = False, True
                return out
            # "noop": log only, keep going
        return out

MAX_REASKS = 2  # hard cap: first attempt + 2 re-asks = at most 3 model calls


class MaxWords(Validator):
    name = "max_words"

    def __init__(self, limit, on_fail="reask"):
        super().__init__(on_fail)
        self.limit = limit

    def validate(self, value):
        n = len(value.split())
        return Result(n <= self.limit, f"reply has {n} words, limit is {self.limit}")


class HasNextStep(Validator):
    name = "has_next_step"

    def validate(self, value):
        ok = bool(re.search(r"\b(please|try|restart|open|reset|contact|call|check|go to)\b", value, re.IGNORECASE))
        return Result(ok, "reply does not tell the user what to do next")


GUARD = Guard("reply-style").use(MaxWords(40)).use(HasNextStep("reask"))
SYSTEM = "You are the Larkspur Labs IT helpdesk assistant."


def guarded_call(ctx, question):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    for attempt in range(1, MAX_REASKS + 2):
        r = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        ctx.record_usage(r.usage, quiet=True)
        reply = r.choices[0].message.content or ""
        out = GUARD.validate(reply)
        ctx.show_data(f"attempt {attempt}", {"reply": reply[:200], "words": len(reply.split()), "log": out.log})
        if not out.reask:
            return reply, attempt, True
        # the heart of re-ask: show the model its own reply and the reason it was rejected
        messages += [
            {"role": "assistant", "content": reply},
            {"role": "user", "content": "That reply was rejected: " + "; ".join(out.reasons) + ". Write a corrected reply."},
        ]
    print(f"  Re-ask cap reached ({MAX_REASKS} re-asks). Giving up and handing over to a human.")
    return reply, attempt, False


@lesson("18.2/3", "Output validation with re-ask")
def main(ctx):
    ctx.step("Validate without a model first")
    for text in ["Restart the router and try again.", "Hello! " + "Thanks for contacting us. " * 15, "It is a known issue."]:
        out = GUARD.validate(text)
        ctx.show_data(text[:40], {"passed": out.passed, "reasons": out.reasons})

    ctx.step("Ask the model, re-ask when the reply breaks the style")
    question = "Explain, with full background and detail, why my laptop is slow after the update."
    reply, attempts, ok = guarded_call(ctx, question)
    print(f"\n  Outcome: {'accepted' if ok else 'NOT accepted'} after {attempts} attempt(s).")
    ctx.note("Re-ask costs a call each time. Cap it, log it, and decide what happens when the cap is hit (here: human).")
    ctx.note("A stub or weak model that never complies ends at the cap: that is the loop working, not failing.")


if __name__ == "__main__":
    main()
