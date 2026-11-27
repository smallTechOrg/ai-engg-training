"""01.3/1  Streaming by hand

In lesson 01.1 a helper printed the stream for you. Here you write the loop yourself and
time it: how long until the first words appear, and how long until the reply is complete.

Run it:   ./run 01.3/1          (Windows: run 01.3/1)
     or:  python modules/01-foundations/03-streaming-and-sampling-parameters/01_streaming_by_hand.py
Add --raw to see the HTTP request and response underneath.
"""

import secrets
import time

from labkit import lesson

PROMPT = "Explain in about 80 words why restarting a computer fixes so many problems."


def fresh_messages():
    """The prompt plus a short random reference.

    Some gateways store answers and replay them instantly for an identical request. The
    reference makes each request unique, so the timings below measure the model, not a cache.
    """
    return [{"role": "user", "content": f"{PROMPT} (Request reference {secrets.token_hex(3)}; ignore it.)"}]


@lesson("01.3/1", "Streaming by hand")
def main(ctx):
    messages = fresh_messages()
    ctx.show_messages(messages)

    ctx.step("Without streaming: wait, then get everything at once")
    started = time.perf_counter()
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    wait_all = time.perf_counter() - started
    ctx.show_response(response)
    ctx.note(f"You saw nothing for {wait_all:.2f}s, then the whole reply.")

    ctx.step("With streaming: read the reply chunk by chunk")
    ctx.note("stream=True returns an iterator. Each chunk carries a small piece of text in choices[0].delta.content.")
    messages = fresh_messages()
    started = time.perf_counter()
    stream = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=messages,
        stream=True,
        stream_options={"include_usage": True},  # ask for token counts in a final chunk
    )

    pieces = []
    first_piece_at = None
    usage = None
    for chunk in stream:
        if chunk.usage:  # the usage chunk comes last and has no choices
            usage = chunk.usage
        for choice in chunk.choices or []:
            piece = choice.delta.content
            if piece:
                if first_piece_at is None:
                    first_piece_at = time.perf_counter() - started
                pieces.append(piece)
                print(piece, end="", flush=True)  # show it the moment it arrives
    total = time.perf_counter() - started
    print()
    ctx.record_usage(usage)  # we handled the stream ourselves, so we report the usage ourselves

    ctx.step("Compare")
    reply = "".join(pieces)
    ctx.show_data(
        "Timings",
        {
            "without streaming: seconds until anything appeared": round(wait_all, 2),
            "with streaming: seconds until the first piece": round(first_piece_at, 2) if first_piece_at is not None else None,
            "with streaming: seconds until complete": round(total, 2),
            "pieces received": len(pieces),
            "characters in the reply": len(reply),
        },
    )
    ctx.note("Streaming does not make the model faster. It lets the reader start reading sooner.")
    ctx.note("The joined pieces are the same kind of string you get without streaming.")


if __name__ == "__main__":
    main()
