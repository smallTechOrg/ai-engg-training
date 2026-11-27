"""00.5/2  Sequential and concurrent model calls, timed

The same idea as the previous script, now with real model calls. Three short questions
are asked one after another, then the same three together with asyncio.gather, and the
two timings are compared. Six small calls in total.

`ctx.async_client` is the asyncio form of the client (`openai.AsyncOpenAI`): identical
methods, but each call is awaited.

Run it:   ./run 00.5/2          (Windows: run 00.5/2)
"""

import asyncio
import time

from labkit import lesson

QUESTIONS = [
    "In one short sentence: what is an API key?",
    "In one short sentence: what is a virtual environment?",
    "In one short sentence: what is an environment variable?",
]


@lesson("00.5/2", "Sequential and concurrent model calls, timed")
async def main(ctx):
    client = ctx.async_client

    async def ask(question: str):
        """One model call. The only difference from module 01 is the word `await`."""
        return await client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "user", "content": question}],
        )

    def show(question: str, response) -> None:
        answer = (response.choices[0].message.content or "").strip()
        ctx.note(f"  Q: {question}")
        ctx.note(f"  A: {answer}")
        ctx.record_usage(response.usage, quiet=True)

    ctx.step("Three questions, one after another")
    started = time.perf_counter()
    for question in QUESTIONS:
        show(question, await ask(question))
    sequential = time.perf_counter() - started
    ctx.note(f"Took {sequential:.1f}s")

    ctx.step("The same three questions, all at once")
    started = time.perf_counter()
    responses = await asyncio.gather(*(ask(question) for question in QUESTIONS))
    concurrent = time.perf_counter() - started
    for question, response in zip(QUESTIONS, responses):
        show(question, response)
    ctx.note(f"Took {concurrent:.1f}s")

    ctx.step("Compare")
    ctx.show_data(
        "Timing for 3 calls",
        {
            "one after another": f"{sequential:.1f}s",
            "all at once": f"{concurrent:.1f}s",
            "speed-up": f"{sequential / concurrent:.1f}x" if concurrent > 0 else "n/a",
        },
    )
    ctx.note("Concurrency changes how long YOU wait. It does not change the tokens used or the cost.")
    ctx.note("Timings vary from run to run: the provider's load is part of every measurement.")

    await client.close()  # release the network connections before the event loop ends


if __name__ == "__main__":
    main()
