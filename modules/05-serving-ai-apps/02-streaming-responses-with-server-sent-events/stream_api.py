"""The streaming helpdesk API used by every script in lesson 05.2.

Lesson 05.1 returned a whole reply as one JSON body. Here the reply is sent as a stream of
Server-Sent Events (SSE): a plain-text format over one long HTTP response.

    event: token
    data: {"text": "Hi "}

    event: done
    data: {"usage": {...}}

Each event is a few lines ending with a blank line. Browsers read it with `EventSource`;
any HTTP client can read it line by line.

Routes:
    GET  /countdown       a model-free stream of numbers (to see the format)
    POST /reply/stream    a ticket in, the assistant's reply out as SSE events
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Annotated

import openai
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Larkspur Labs helpdesk API (streaming)", version="0.2.0")

# Set by a script that wants to observe what happens on the server side of a stream.
server_log: list[str] = []


class TicketIn(BaseModel):
    ticket_id: str = Field(pattern=r"^LL-\d{4}$", examples=["LL-2001"])
    employee: str = Field(min_length=1, examples=["Priya (Finance)"])
    text: str = Field(min_length=10)


def get_llm() -> openai.OpenAI:
    from labkit import get_client, load_settings

    return get_client(load_settings().require())


def get_model() -> str:
    from labkit import load_settings

    return load_settings().require().model


LLM = Annotated[openai.OpenAI, Depends(get_llm)]
ModelName = Annotated[str, Depends(get_model)]

REPLY_PROMPT = """You are the first-line IT helpdesk assistant at Larkspur Labs.
Reply to the employee in at most four short sentences, addressed to them by first name.
Give one concrete thing to try first. Be friendly and plain; no jargon."""


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event: an event name, a JSON data line, and a blank line."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/countdown")
def countdown(start: int = 3) -> StreamingResponse:
    def events() -> Iterator[str]:
        for n in range(start, 0, -1):
            yield sse("tick", {"n": n})
            time.sleep(0.05)
        yield sse("done", {"message": "liftoff"})

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/reply/stream")
def reply_stream(ticket: TicketIn, llm: LLM, model: ModelName) -> StreamingResponse:
    messages = [
        {"role": "system", "content": REPLY_PROMPT},
        {"role": "user", "content": f"Ticket {ticket.ticket_id} from {ticket.employee}:\n{ticket.text}"},
    ]

    def events() -> Iterator[str]:
        started = time.perf_counter()
        first_token_s = None
        usage = None
        stream = None
        try:
            # The model call is made INSIDE the generator, after the 200 status line has
            # already gone out. A failure here cannot become a 502: it has to become an event.
            stream = llm.chat.completions.create(
                model=model, messages=messages, stream=True, stream_options={"include_usage": True}
            )
            for chunk in stream:
                if chunk.usage:
                    usage = {"prompt_tokens": chunk.usage.prompt_tokens, "completion_tokens": chunk.usage.completion_tokens}
                for choice in chunk.choices or []:
                    if choice.delta.content:
                        if first_token_s is None:
                            first_token_s = round(time.perf_counter() - started, 3)
                        yield sse("token", {"text": choice.delta.content})
            yield sse("done", {"ticket_id": ticket.ticket_id, "usage": usage, "first_token_s": first_token_s})
        except openai.OpenAIError as error:
            detail = " ".join(str(error).split())[:200]
            yield sse("error", {"message": f"The model endpoint failed: {type(error).__name__}: {detail}"})
        finally:
            # Runs when the stream ends normally, fails, or the client disconnects.
            if stream is not None:
                stream.close()
            server_log.append(f"{ticket.ticket_id}: generator closed, upstream stream released")

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},  # tell proxies not to buffer
    )
