"""00.5/1  Waiting for several things at once

A model call is mostly waiting: your program sends a request and then does nothing for a
second or more. asyncio lets one program wait for many things at the same time. This
script uses pretend calls (asyncio.sleep), so you can see how it works with no model and
no cost: three waits one after another, then the same three together.

Run it:   ./run 00.5/1          (Windows: run 00.5/1)
     or:  python modules/00-setup/05-async-python/01_asyncio_basics.py
"""

import asyncio
import time

from labkit import lesson

# (name, seconds it takes to "answer")
PRETEND_CALLS = [("call A", 0.6), ("call B", 0.4), ("call C", 0.5)]


async def pretend_call(name: str, seconds: float, started: float, ctx) -> str:
    """Stands in for a model call: all it does is wait."""
    ctx.note(f"  {time.perf_counter() - started:4.1f}s  {name} sent")
    await asyncio.sleep(seconds)  # `await` hands control back so other work can proceed
    ctx.note(f"  {time.perf_counter() - started:4.1f}s  {name} answered")
    return f"{name} result"


@lesson("00.5/1", "Waiting for several things at once")
async def main(ctx):
    ctx.step("One after another")
    ctx.note("Each `await` finishes before the next call starts. Total time = the sum of the waits.")
    started = time.perf_counter()
    results = []
    for name, seconds in PRETEND_CALLS:
        results.append(await pretend_call(name, seconds, started, ctx))
    sequential = time.perf_counter() - started
    ctx.note(f"Took {sequential:.1f}s. Results: {results}")

    ctx.step("All at once with asyncio.gather")
    ctx.note("gather starts every call, then waits for all of them. Total time = the longest wait.")
    started = time.perf_counter()
    results = await asyncio.gather(*(pretend_call(name, seconds, started, ctx) for name, seconds in PRETEND_CALLS))
    concurrent = time.perf_counter() - started
    ctx.note(f"Took {concurrent:.1f}s. Results: {list(results)}")
    ctx.note("Results come back in the order you asked, not the order they finished (B answered first).")

    ctx.step("What just happened")
    ctx.show_data(
        "Comparison",
        {
            "one after another": f"{sequential:.1f}s",
            "all at once": f"{concurrent:.1f}s",
            "speed-up": f"{sequential / concurrent:.1f}x" if concurrent else "n/a",
        },
    )
    ctx.note("Nothing ran in parallel on several CPU cores. One thread just stopped sitting idle while it waited.")
    ctx.note("That is why asyncio suits model calls (waiting) and does nothing for heavy computation.")


if __name__ == "__main__":
    main()
