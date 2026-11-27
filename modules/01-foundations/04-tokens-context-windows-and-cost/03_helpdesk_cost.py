"""01.4/3  What a helpdesk reply costs

Providers charge per token. Input (prompt) tokens and output (completion) tokens have
separate prices, usually quoted per million tokens. This script answers one ticket, takes
the real token counts from the response, and turns them into money: per ticket, per 10,000
tickets, and what a longer system prompt would add.

The prices below are EXAMPLES, not any provider's real prices. Edit them to match yours.

One model call.

Run it:   ./run 01.4/3          (Windows: run 01.4/3)
"""

from labkit import lesson

# --- example prices: edit for your provider ------------------------------------------
# Invented numbers in US dollars per 1,000,000 tokens, chosen only to make the arithmetic
# realistic. Look up your provider's price list and put the real values here.
EXAMPLE_PRICE_INPUT_PER_MILLION = 0.50
EXAMPLE_PRICE_OUTPUT_PER_MILLION = 1.50
# --------------------------------------------------------------------------------------

TICKETS_PER_MONTH = 10_000

SYSTEM_PROMPT = """You are the first-line IT helpdesk assistant at Larkspur Labs.
Reply to the employee in at most four short sentences.
Give one concrete thing to try first. If it might not work, say what you will do next."""

TICKET = """Ticket #6203 from Tomas (Logistics):
Outlook keeps asking for my password every few minutes since this morning. I type it in and
it works for a bit, then asks again. Webmail in the browser is fine."""

# Text a team might be tempted to paste into every system prompt "just in case".
EXTRA_POLICY = """
Larkspur Labs IT policy summary (always follow):
1. Never ask for or accept a password in a ticket. Direct the employee to the self-service reset page.
2. Laptops are replaced every four years; earlier replacement needs a manager's approval.
3. Software not on the approved catalogue needs a security review, which takes five working days.
4. Lost or stolen devices must be reported within one hour; IT will wipe them remotely.
5. VPN is required for all access to internal systems from outside the office network.
6. Printer problems on floors 1-3 go to Facilities first; IT handles drivers and print queues only.
7. Shared mailboxes are requested by a team lead, never by individual employees.
8. Multi-factor authentication resets require a video call with the service desk to verify identity.
9. Personal phones may receive company email only with the device management app installed.
10. Escalate anything that mentions customer data, a security incident or a legal hold immediately.
"""


def estimate_tokens(text):
    return max(1, round(len(text) / 4))


def cost(tokens_in, tokens_out):
    """Dollars for one call at the example prices."""
    return (tokens_in * EXAMPLE_PRICE_INPUT_PER_MILLION + tokens_out * EXAMPLE_PRICE_OUTPUT_PER_MILLION) / 1_000_000


@lesson("01.4/3", "What a helpdesk reply costs")
def main(ctx):
    ctx.step("Answer one ticket")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TICKET},
    ]
    ctx.show_messages(messages)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    reply = ctx.show_response(response)

    ctx.step("Read the usage")
    prompt_chars = sum(len(m["content"]) for m in messages)
    usage = response.usage
    if usage is not None and usage.prompt_tokens is not None and usage.completion_tokens is not None:
        tokens_in, tokens_out, how = usage.prompt_tokens, usage.completion_tokens, "reported by the endpoint"
    else:
        tokens_in, tokens_out, how = estimate_tokens(SYSTEM_PROMPT + TICKET), estimate_tokens(reply), "estimated (characters / 4)"
        ctx.note("This endpoint reported no usage, so the numbers below are characters / 4 estimates.")
        ctx.note("Your provider's bill will use its own count; check its dashboard for the real figure.")
    ctx.note(f"Input: {tokens_in} tokens. Output: {tokens_out} tokens. Source: {how}.")

    ctx.step("Turn tokens into money")
    ctx.note(f"Example prices (edit for your provider): ${EXAMPLE_PRICE_INPUT_PER_MILLION:.2f} per million input tokens, "
             f"${EXAMPLE_PRICE_OUTPUT_PER_MILLION:.2f} per million output tokens.")
    input_cost = tokens_in * EXAMPLE_PRICE_INPUT_PER_MILLION / 1_000_000
    output_cost = tokens_out * EXAMPLE_PRICE_OUTPUT_PER_MILLION / 1_000_000
    per_ticket = input_cost + output_cost
    ctx.console.print(f"  input   {tokens_in:>6} tokens  ${input_cost:.6f}", markup=False)
    ctx.console.print(f"  output  {tokens_out:>6} tokens  ${output_cost:.6f}", markup=False)
    ctx.console.print(f"  one ticket              ${per_ticket:.6f}", markup=False)
    ctx.console.print(f"  {TICKETS_PER_MONTH:,} tickets          ${per_ticket * TICKETS_PER_MONTH:.2f}", markup=False)
    if per_ticket > 0:
        share = 100 * output_cost / per_ticket
        ratio = EXAMPLE_PRICE_OUTPUT_PER_MILLION / EXAMPLE_PRICE_INPUT_PER_MILLION
        ctx.note(f"Output is {share:.0f}% of this ticket's cost. Each output token costs {ratio:g}x an input token,")
        ctx.note("so asking for short replies saves more per token than trimming the prompt.")

    ctx.step("What a longer system prompt adds")
    # Calibrate characters-per-token on this request, so the estimate fits this model's tokenizer.
    chars_per_token, source = 4.0, "the usual rule of thumb"
    if how.startswith("reported") and tokens_in and 1.5 <= prompt_chars / tokens_in <= 8:
        chars_per_token, source = prompt_chars / tokens_in, "measured on the request above"
    elif how.startswith("reported"):
        ctx.note(f"The reported count ({tokens_in} tokens for {prompt_chars} characters) is implausible, so we use 4 characters per token.")
    extra_tokens = round(len(EXTRA_POLICY) / chars_per_token)
    ctx.note(f"Suppose we paste a {len(EXTRA_POLICY):,}-character policy summary into the system prompt.")
    ctx.note(f"At {chars_per_token:.1f} characters per token ({source}), that is about {extra_tokens} more input tokens.")
    longer = cost(tokens_in + extra_tokens, tokens_out)
    handbook = cost(tokens_in + 10 * extra_tokens, tokens_out)
    rows = [
        ("as sent", tokens_in, per_ticket),
        ("+ policy summary", tokens_in + extra_tokens, longer),
        ("+ 10x that (a handbook)", tokens_in + 10 * extra_tokens, handbook),
    ]
    ctx.console.print(f"  {'system prompt':<24} {'input tokens':>12} {'per ticket':>12} {'per ' + format(TICKETS_PER_MONTH, ',') + ' tickets':>18}", markup=False)
    for name, count, dollars in rows:
        ctx.console.print(f"  {name:<24} {count:>12} {'$' + format(dollars, '.6f'):>12} {'$' + format(dollars * TICKETS_PER_MONTH, '.2f'):>18}", markup=False)
    if per_ticket > 0:
        ctx.note(f"The system prompt is sent with every ticket: the policy summary alone multiplies the cost by {longer / per_ticket:.1f}x.")
    ctx.note("Every word of a system prompt is paid for on every call. Keep it to what changes the answer;")
    ctx.note("some providers discount repeated prompt prefixes (prompt caching), which is worth checking.")


if __name__ == "__main__":
    main()
