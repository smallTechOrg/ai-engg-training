"""The Larkspur Labs helpdesk service: the capstone API (lesson 05.5).

It combines the module: validated models and dependency injection (05.1), Server-Sent Events
(05.2). The chat page in chat_page.py is its only front end.

    GET  /health        is the service up?
    POST /triage        a ticket in, a validated triage out        (one model call, JSON schema)
    POST /chat/stream   a conversation in, the next reply as SSE   (one streaming model call)
    GET  /stats         requests served and token usage so far

Run it for real, from the repo root:
    uv run uvicorn helpdesk_service:app --app-dir modules/05-serving-ai-apps/05-capstone-helpdesk-assistant-as-an-api-with-a-cha
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Annotated, Literal

import openai
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

app = FastAPI(title="Larkspur Labs helpdesk service", version="1.0.0")

stats: dict = {"requests": 0, "usage": []}  # in memory; a real service would export metrics (module 17)


def reset_stats() -> None:
    stats["requests"] = 0
    stats["usage"] = []


# --- models ---------------------------------------------------------------------------


class TicketIn(BaseModel):
    ticket_id: str = Field(pattern=r"^LL-\d{4}$", examples=["LL-3001"])
    employee: str = Field(min_length=1, examples=["Priya (Finance)"])
    text: str = Field(min_length=10)


class Triage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["network", "hardware", "software", "access", "other"]
    urgency: Literal["low", "medium", "high"]
    summary: str
    needs_human: bool


class TriageOut(BaseModel):
    ticket_id: str
    triage: Triage
    usage: dict | None


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatIn(BaseModel):
    employee: str = Field(default="", max_length=80)
    messages: list[Message] = Field(min_length=1, max_length=40)

    @field_validator("messages")
    @classmethod
    def last_is_user(cls, messages: list[Message]) -> list[Message]:
        if messages[-1].role != "user":
            raise ValueError("the last message must come from the user")
        return messages


# --- dependencies ---------------------------------------------------------------------


def get_llm() -> openai.OpenAI:
    from labkit import get_client, load_settings

    return get_client(load_settings().require())


def get_model() -> str:
    from labkit import load_settings

    return load_settings().require().model


LLM = Annotated[openai.OpenAI, Depends(get_llm)]
ModelName = Annotated[str, Depends(get_model)]

CHAT_PROMPT = """You are the first-line IT helpdesk assistant at Larkspur Labs.
Answer in at most three short sentences, address the employee by first name when you know it,
give one concrete thing to try, and use what they already told you earlier in the conversation."""

TRIAGE_PROMPT = """You triage IT helpdesk tickets for Larkspur Labs.
category: network (Wi-Fi, VPN), hardware (physical devices), software (apps, updates),
access (accounts, passwords, permissions), other (not an IT problem).
urgency: high if it blocks work today or affects many people, low if it can wait days.
summary is one sentence. needs_human is true when a person must act (visit, repair, approval, unlock)."""


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def error_text(error: Exception) -> str:
    return f"The model endpoint failed: {type(error).__name__}: {' '.join(str(error).split())[:160]}"


def usage_dict(usage) -> dict | None:
    if usage is None:
        return None
    return {"prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens}


# --- routes ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "helpdesk-service"}


@app.get("/stats")
def get_stats() -> dict:
    return stats


@app.post("/triage", response_model=TriageOut)
def triage(ticket: TicketIn, llm: LLM, model: ModelName) -> TriageOut:
    stats["requests"] += 1
    try:
        response = llm.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": TRIAGE_PROMPT},
                {"role": "user", "content": f'<ticket id="{ticket.ticket_id}" from="{ticket.employee}">\n{ticket.text}\n</ticket>'},
            ],
            response_format={"type": "json_schema", "json_schema": {"name": "triage", "schema": Triage.model_json_schema(), "strict": True}},
            temperature=0,
        )
    except openai.OpenAIError as error:
        raise HTTPException(status_code=502, detail=error_text(error)) from error
    usage = usage_dict(response.usage)
    stats["usage"].append(usage)
    try:
        result = Triage.model_validate_json(response.choices[0].message.content or "")
    except ValidationError as error:
        raise HTTPException(status_code=502, detail={"problem": "model reply did not match the Triage schema", "errors": json.loads(error.json())[:3]}) from error
    return TriageOut(ticket_id=ticket.ticket_id, triage=result, usage=usage)


@app.post("/chat/stream")
def chat_stream(chat: ChatIn, llm: LLM, model: ModelName) -> StreamingResponse:
    stats["requests"] += 1
    who = f" You are talking to {chat.employee}." if chat.employee else ""
    messages = [{"role": "system", "content": CHAT_PROMPT + who}] + [m.model_dump() for m in chat.messages]

    def events() -> Iterator[str]:
        started = time.perf_counter()
        first = None
        usage = None
        stream = None
        try:
            stream = llm.chat.completions.create(model=model, messages=messages, stream=True, stream_options={"include_usage": True})
            for chunk in stream:
                if chunk.usage:
                    usage = usage_dict(chunk.usage)
                for choice in chunk.choices or []:
                    if choice.delta.content:
                        if first is None:
                            first = round(time.perf_counter() - started, 3)
                        yield sse("token", {"text": choice.delta.content})
            stats["usage"].append(usage)
            yield sse("done", {"usage": usage, "first_token_s": first, "history_messages": len(chat.messages)})
        except openai.OpenAIError as error:
            yield sse("error", {"message": error_text(error)})
        finally:
            if stream is not None:
                stream.close()

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
