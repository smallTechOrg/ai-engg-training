"""01.5/2  Chain-of-thought

The same question asked two ways:

  direct:           "reply with only the number";
  chain-of-thought: "work through it step by step, then give the final answer".

A model writes its answer one token at a time. Asking for the steps first means the answer
is written *after* the working, so it can depend on it. The price is more output tokens.

Run it:   ./run 01.5/2          (Windows: run 01.5/2)
"""

import re

from labkit import lesson

PROBLEM = """Larkspur Labs owns 120 licence seats for its design tool.
97 seats are assigned today.
At the end of the month 9 people leave and their seats are freed.
3 of those freed seats are reserved for contractors and cannot be reassigned.
Next month 34 new starters each need a seat.
How many additional seats must IT buy?"""

CORRECT = 5  # 120 - 97 = 23 free; + 9 freed = 32; - 3 reserved = 29; 34 - 29 = 5


def final_number(reply):
    """Find the answer tolerantly: an 'Answer:' line if there is one, else the last number."""
    answer_lines = re.findall(r"answer\W*?(-?\d+)", reply, flags=re.IGNORECASE)
    if answer_lines:
        return int(answer_lines[-1])
    numbers = re.findall(r"-?\d+", reply)
    return int(numbers[-1]) if numbers else None


def verdict(number):
    if number is None:
        return "no number found in the reply"
    return f"{number} ({'correct' if number == CORRECT else f'wrong, expected {CORRECT}'})"


@lesson("01.5/2", "Chain-of-thought")
def main(ctx):
    ctx.step("Ask directly")
    direct = [{"role": "user", "content": PROBLEM + "\n\nReply with only the number."}]
    ctx.show_messages(direct)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=direct)
    direct_reply = ctx.show_response(response)
    direct_tokens = getattr(response.usage, "completion_tokens", None)

    ctx.step("Ask for the reasoning first")
    ctx.note("Only the last sentence of the prompt changes.")
    stepwise = [
        {
            "role": "user",
            "content": PROBLEM + "\n\nWork through it step by step, one short line per step. "
            "Then finish with a final line in exactly this form: Answer: <number>",
        }
    ]
    response = ctx.client.chat.completions.create(model=ctx.model, messages=stepwise)
    stepwise_reply = ctx.show_response(response)
    stepwise_tokens = getattr(response.usage, "completion_tokens", None)

    ctx.step("Compare answers and cost")
    ctx.show_data(
        "Result",
        {
            "direct": {"answer": verdict(final_number(direct_reply)), "output_tokens": direct_tokens},
            "step by step": {"answer": verdict(final_number(stepwise_reply)), "output_tokens": stepwise_tokens},
        },
    )
    ctx.note("Smaller models often get the direct version wrong; stronger ones may get both right. Either way the step-by-step version gives you working you can check, at the price of more output tokens.")
    ctx.note("We parse the 'Answer:' line instead of trusting the whole reply: ask for a fixed final line whenever code has to read the result.")


if __name__ == "__main__":
    main()
