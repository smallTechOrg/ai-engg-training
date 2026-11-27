"""01.4/1  Tokens are not words

Models do not read characters or words; they read tokens, pieces of text from a fixed
vocabulary. The endpoint tells you how many it counted in `response.usage`, and that count
is what you are billed for and what fills the context window.

This script first sends a short instruction on its own (the baseline, which also shows the
fixed overhead every request carries), then four short texts after that same instruction,
one per call, and puts three guesses (characters, words, characters / 4) next to the real
prompt_tokens. Five calls in all.

No tokenizer package is used: tokenizers differ between providers, and the endpoint's own
count is the only number that is always right for the model you are using.

Run it:   ./run 01.4/1          (Windows: run 01.4/1)
     or:  python modules/01-foundations/04-tokens-context-windows-and-cost/01_tokens_are_not_words.py
Add --raw to see the HTTP request and response underneath.
"""

from labkit import lesson

# Each text is roughly the same length in characters. Watch how differently they tokenize.
SAMPLES = [
    ("English prose", "The printer on the third floor jams every morning, so please send someone to look at it."),
    ("Python code", "def total(xs):\n    return sum(x * 1.2 for x in xs if x > 0)  # add VAT"),
    ("Non-English", "Die Druckerin im dritten Stock blockiert jeden Morgen; bitte schicken Sie jemanden vorbei."),
    ("Numbers", "4821 5127 5130 90210 3.14159 2718281828 1000000 42 7 365 86400 65535"),
]

INSTRUCTION = "Reply with only the word OK. Text follows:\n"


def estimate(text):
    """The common rule of thumb for English: about four characters per token."""
    return max(1, round(len(text) / 4))


@lesson("01.4/1", "Tokens are not words")
def main(ctx):
    ctx.step("Measure the instruction on its own")
    ctx.note("Every sample is sent after the same short instruction. Send the instruction alone first:")
    ctx.note("its prompt_tokens is the baseline we subtract later to find the tokens of each sample.")
    messages = [{"role": "user", "content": INSTRUCTION}]
    ctx.show_messages(messages)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    ctx.show_response(response)
    baseline = response.usage.prompt_tokens if response.usage else None
    if baseline is None:
        ctx.note("This endpoint does not report usage, so the real columns below will say 'n/a'.")
        ctx.note("The estimate still works: it needs no endpoint at all.")
    else:
        guess = estimate(INSTRUCTION)
        ctx.note(f"Baseline: {baseline} prompt tokens. Characters / 4 guesses {guess} for the instruction text.")
        ctx.note("prompt_tokens also includes a fixed per-request overhead: role markers and the chat template")
        ctx.note("the provider wraps around every message. Some providers add several tokens per message, some")
        ctx.note(f"almost none (here: about {max(0, baseline - guess)} beyond the guess). You pay it on every call, even a")
        ctx.note("one-word one. Subtracting the baseline removes it, along with the instruction, from the samples.")

    rows = []
    for label, text in SAMPLES:
        ctx.step(f"Send: {label}")
        messages = [{"role": "user", "content": INSTRUCTION + text}]
        ctx.show_messages(messages)
        # We only want the count, so the reply is kept tiny: the prompt asks for one word.
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        ctx.record_usage(response.usage)
        real = response.usage.prompt_tokens if response.usage else None
        rows.append((label, text, real))

    ctx.step("Compare the guesses with the real count")
    ctx.note("'text tokens' = prompt_tokens minus the baseline: the tokens of the sample text alone.")
    header = f"{'text':<14} {'chars':>5} {'words':>5} {'chars/4':>7} {'prompt_tokens':>13} {'text tokens':>11} {'chars/token':>11}"
    ctx.console.print(header, markup=False)
    ctx.console.print("-" * len(header), markup=False)
    for label, text, real in rows:
        chars, words, guess = len(text), len(text.split()), estimate(text)
        if real is None:
            real_s, own_s, ratio_s = "n/a", "n/a", "n/a"
        else:
            own = real - baseline if baseline is not None else None
            ratio_s = f"{chars / own:.1f}" if own and own > 0 else "n/a"
            real_s, own_s = str(real), str(own) if own is not None else "n/a"
        ctx.console.print(f"{label:<14} {chars:>5} {words:>5} {guess:>7} {real_s:>13} {own_s:>11} {ratio_s:>11}", markup=False)

    ctx.step("What to take away")
    ctx.note("English prose is close to 4 characters per token. Code and numbers usually are not: symbols,")
    ctx.note("indentation and digit runs are split into more, smaller pieces (some tokenizers split every digit).")
    ctx.note("Other languages depend on the tokenizer: German is often close to English on modern models, while")
    ctx.note("languages in other scripts can take two or three times as many tokens for the same meaning.")
    ctx.note("Words are a poor guide; characters / 4 is a fair first guess for English only.")
    ctx.note("For anything that matters (cost, fitting the context window), use the count the endpoint reports.")
    if any(real is not None and real == baseline for _, _, real in rows):
        ctx.note("Some samples cost no more than the baseline: this endpoint reports the same count for every")
        ctx.note("request (a test stub does this). A real provider counts each text differently.")
    if any(real is None for _, _, real in rows):
        ctx.note("Your endpoint reported no usage, so here the estimate is all you have. Treat it as rough.")


if __name__ == "__main__":
    main()
