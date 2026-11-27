"""17.3/2  A budget guard that stops a loop

A loop that calls a model (an agent, a retry loop, a reflection loop) can run away and keep
spending. A BudgetGuard wraps each call. It checks BEFORE the call that there is budget left,
adds the cost AFTER, and refuses more calls once a cap is reached. There are three caps:
dollars, tokens and calls.

If an endpoint reports no token counts, the guard estimates them from the text length (about 4
characters per token), so the budget still holds. The prices are INVENTED constants.

Run it:   ./run 17.3/2          (Windows: run 17.3/2)
     or:  python modules/17-monitoring-and-fine-tuning/03-cost-tracking-budgets-and-service-level-objectiv/02_budget_guard.py
"""

from labkit import lesson

PRICE_IN_PER_M = 0.50
PRICE_OUT_PER_M = 1.50


class BudgetExceeded(Exception):
    """Raised before a call that would go over a cap."""


class BudgetGuard:
    def __init__(self, max_dollars, max_tokens, max_calls):
        self.max_dollars, self.max_tokens, self.max_calls = max_dollars, max_tokens, max_calls
        self.dollars = 0.0
        self.tokens = 0
        self.calls = 0
        self.estimated_calls = 0

    def check(self):
        """Call before every model call."""
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"call cap reached ({self.calls}/{self.max_calls})")
        if self.tokens >= self.max_tokens:
            raise BudgetExceeded(f"token cap reached ({self.tokens}/{self.max_tokens})")
        if self.dollars >= self.max_dollars:
            raise BudgetExceeded(f"dollar cap reached (${self.dollars:.6f}/${self.max_dollars:.6f})")

    def charge(self, usage, prompt_text, reply_text):
        """Call after every model call. Uses the reported usage, or estimates from text length."""
        t_in = getattr(usage, "prompt_tokens", None)
        t_out = getattr(usage, "completion_tokens", None)
        if t_in is None or t_out is None:
            t_in, t_out = max(1, len(prompt_text) // 4), max(1, len(reply_text) // 4)
            self.estimated_calls += 1
        self.calls += 1
        self.tokens += t_in + t_out
        self.dollars += t_in * PRICE_IN_PER_M / 1e6 + t_out * PRICE_OUT_PER_M / 1e6
        return t_in, t_out

    def remaining(self):
        return f"${max(0.0, self.max_dollars - self.dollars):.6f}, {max(0, self.max_tokens - self.tokens)} tokens, {self.max_calls - self.calls} calls"


@lesson("17.3/2", "A budget guard that stops a loop")
def main(ctx):
    ctx.step("Create a guard with a deliberately small budget")
    guard = BudgetGuard(max_dollars=0.0005, max_tokens=150, max_calls=6)
    ctx.note(f"caps: ${guard.max_dollars}, {guard.max_tokens} tokens, {guard.max_calls} calls. A runaway 'keep improving the reply' loop would never stop by itself.")

    ctx.step("Run a refine loop: ask for a better reply until the guard says stop")
    reply = "Restart the router."
    HARD_CAP = 10  # the loop's own limit: the guard is a backup, not the only protection
    stopped = None
    for i in range(1, HARD_CAP + 1):
        prompt = f"Make this IT helpdesk reply friendlier and more specific, in one sentence: {reply}"
        try:
            guard.check()
        except BudgetExceeded as exc:
            stopped = str(exc)
            ctx.note(f"iteration {i}: BLOCKED before calling the model: {stopped}")
            break
        r = ctx.client.chat.completions.create(model=ctx.model, messages=[{"role": "user", "content": prompt}])
        reply = r.choices[0].message.content or reply
        t_in, t_out = guard.charge(r.usage, prompt, reply)
        ctx.record_usage(r.usage, quiet=True)
        ctx.console.print(f"iteration {i}: {t_in} in + {t_out} out | left: {guard.remaining()}", markup=False)
    else:
        ctx.note(f"the loop's own cap of {HARD_CAP} iterations ended it; the guard never fired")

    ctx.step("What the guard saw")
    ctx.note(f"{guard.calls} calls, {guard.tokens} tokens, about ${guard.dollars:.6f}. {guard.estimated_calls} call(s) were estimated from text length because the endpoint reported no usage.")
    ctx.note("Final reply: " + reply[:160])
    ctx.note("Design choices: check BEFORE the call, so a spent budget never starts another call. The last allowed call can still overshoot a cap, as iteration 3 did, so leave headroom. Raise a specific exception and let the caller decide: return the best reply so far, switch to a cheaper model, or ask a human.")
    ctx.note("A guard in one process is not a company budget. To cap spend across workers, keep the total in shared storage (Redis, a database).")


if __name__ == "__main__":
    main()
