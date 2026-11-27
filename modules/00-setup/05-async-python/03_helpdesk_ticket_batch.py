"""00.5/3  The helpdesk assistant answers a batch of tickets

Monday morning at Larkspur Labs: five tickets are waiting. Answering them one at a time
keeps the fifth employee waiting for no reason. Sending fifty at once would hit the
provider's rate limit (the cap on how many requests you may send). This script answers the
five concurrently, but never more than two at a time, using a semaphore. If one ticket
fails, the rest are still answered.

Run it:   ./run 00.5/3          (Windows: run 00.5/3)
"""

import asyncio
import time

from labkit import lesson

SYSTEM_PROMPT = """You are the first-line IT helpdesk assistant at Larkspur Labs.
Reply to the employee in at most two short sentences with one concrete thing to try."""

TICKETS = [
    ("#5001", "Tomas (Sales)", "I forgot my password and I am locked out of email."),
    ("#5002", "Aiko (Design)", "The office printer on floor 2 prints blank pages."),
    ("#5003", "Priya (Finance)", "The VPN disconnects every few minutes when I work from home."),
    ("#5004", "Lukas (Legal)", "My laptop fan is very loud and the machine is slow."),
    ("#5005", "Sara (HR)", "I cannot open the shared drive; it says access denied."),
]

MAX_AT_ONCE = 2  # how many calls may be in flight together
MAX_TICKETS = 5  # hard cap on the batch, so a mistake cannot send hundreds of calls


@lesson("00.5/3", "The helpdesk assistant answers a batch of tickets")
async def main(ctx):
    client = ctx.async_client
    tickets = TICKETS[:MAX_TICKETS]
    limit = asyncio.Semaphore(MAX_AT_ONCE)
    started = time.perf_counter()

    async def answer(ticket_id: str, who: str, problem: str):
        """Answer one ticket. `async with limit` waits here until a slot is free."""
        async with limit:
            ctx.note(f"  {time.perf_counter() - started:4.1f}s  {ticket_id} started")
            response = await client.chat.completions.create(
                model=ctx.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Ticket {ticket_id} from {who}: {problem}"},
                ],
            )
            ctx.note(f"  {time.perf_counter() - started:4.1f}s  {ticket_id} answered")
            return response

    ctx.step("The queue")
    for ticket_id, who, problem in tickets:
        ctx.note(f"  {ticket_id}  {who}: {problem}")

    ctx.step(f"Answer all {len(tickets)}, at most {MAX_AT_ONCE} at a time")
    ctx.note("Watch the timestamps: a new ticket starts only when an earlier one is answered.")
    # return_exceptions=True: a failed ticket comes back as an exception object instead of
    # cancelling the others.
    results = await asyncio.gather(*(answer(*ticket) for ticket in tickets), return_exceptions=True)
    elapsed = time.perf_counter() - started

    ctx.step("The replies")
    failures = [result for result in results if isinstance(result, Exception)]
    for (ticket_id, who, _), result in zip(tickets, results):
        if isinstance(result, Exception):
            ctx.note(f"  {ticket_id} to {who}: FAILED ({type(result).__name__})")
            continue
        reply = (result.choices[0].message.content or "").strip()
        ctx.note(f"  {ticket_id} to {who}: {reply}")
        ctx.record_usage(result.usage, quiet=True)

    ctx.step("How it went")
    ctx.show_data(
        "Batch",
        {
            "tickets": len(tickets),
            "answered": len(tickets) - len(failures),
            "failed": len(failures),
            "at most in flight": MAX_AT_ONCE,
            "total time": f"{elapsed:.1f}s",
        },
    )
    await client.close()
    if failures and len(failures) == len(tickets):
        raise failures[0]  # nothing worked: let the lesson runtime explain why (bad key, no network...)


if __name__ == "__main__":
    main()
