"""The Larkspur Labs helpdesk API, used by every script in lesson 05.1.

This file is an ordinary FastAPI application. The lesson scripts import it and call it
in-process with `fastapi.testclient.TestClient` (no port, no server to start). To run it
as a real web server instead, from the top of the repo:

    uv run uvicorn helpdesk_api:app --reload --app-dir modules/05-serving-ai-apps/01-rest-and-fastapi-basics-with-pydantic-models

then open http://127.0.0.1:8000/docs in a browser.

Routes:
    GET  /health   is the service up?                       (no model)
    POST /echo     validates the body and echoes it back     (no model)
    POST /reply    a ticket in, the assistant's reply out    (one model call)
    POST /triage   a ticket in, a validated triage out       (one model call, JSON schema)
"""

from __future__ import annotations

import json
from typing import Annotated, Literal

import openai
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

# --- request and response models ------------------------------------------------------
# Each class is both validation (FastAPI rejects bad input with 422 before your code runs)
# and documentation (FastAPI turns it into the OpenAPI schema shown at /docs).


class Health(BaseModel):
    status: Literal["ok"]
    service: str


class EchoIn(BaseModel):
    message: str = Field(min_length=1, max_length=200, description="Any text.")
    repeat: int = Field(default=1, ge=1, le=3, description="How many times to echo it (1-3).")


class EchoOut(BaseModel):
    echoed: list[str]
    length: int


class TicketIn(BaseModel):
    ticket_id: str = Field(pattern=r"^LL-\d{4}$", examples=["LL-2001"])
    employee: str = Field(min_length=1, examples=["Priya (Finance)"])
    text: str = Field(min_length=10, examples=["My laptop will not connect to the office Wi-Fi."])


class Usage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ReplyOut(BaseModel):
    ticket_id: str
    reply: str
    model: str
    usage: Usage | None = Field(description="Token counts for the model call; null if the provider did not report them.")


class Triage(BaseModel):
    """The structured result the rest of the helpdesk system needs (as in lesson 01.6)."""

    model_config = ConfigDict(extra="forbid")  # strict JSON schema: no extra keys

    category: Literal["network", "hardware", "software", "access", "other"]
    urgency: Literal["low", "medium", "high"]
    summary: str
    needs_human: bool


class TriageOut(BaseModel):
    ticket_id: str
    triage: Triage
    usage: Usage | None


# --- dependencies ---------------------------------------------------------------------
# A dependency is a function FastAPI calls for you and passes into the route. Routes ask
# for "an LLM client" and "a model name" and do not care where they come from. Tests (and
# the lesson scripts) swap them with app.dependency_overrides, without touching the routes.


def get_llm() -> openai.OpenAI:
    """The real client, built from the course settings in .env."""
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

TRIAGE_PROMPT = """You triage IT helpdesk tickets for Larkspur Labs.
category: network (Wi-Fi, VPN), hardware (physical devices), software (apps, updates),
access (accounts, passwords, permissions), other (not an IT problem).
urgency: high if it blocks work today or affects many people, low if it can wait days.
summary is one sentence. needs_human is true when a person must act (visit, repair, approval, unlock)."""

app = FastAPI(
    title="Larkspur Labs helpdesk API",
    version="0.1.0",
    description="Lesson 05.1: a model behind a small, validated REST API.",
)


def usage_of(response) -> Usage | None:
    if response.usage is None:
        return None
    return Usage(prompt_tokens=response.usage.prompt_tokens, completion_tokens=response.usage.completion_tokens)


def upstream_error(error: Exception) -> HTTPException:
    """The model endpoint failed: that is a 502 (bad gateway) for our caller, not a 500."""
    detail = " ".join(str(error).split())[:200]
    return HTTPException(status_code=502, detail=f"The model endpoint failed: {type(error).__name__}: {detail}")


# --- routes ---------------------------------------------------------------------------


@app.get("/health", response_model=Health, tags=["basics"])
def health() -> Health:
    return Health(status="ok", service="helpdesk-api")


@app.post("/echo", response_model=EchoOut, tags=["basics"])
def echo(body: EchoIn) -> EchoOut:
    # By the time this line runs, FastAPI has already parsed and validated `body`.
    return EchoOut(echoed=[body.message] * body.repeat, length=len(body.message))


@app.post("/reply", response_model=ReplyOut, tags=["assistant"])
def reply(ticket: TicketIn, llm: LLM, model: ModelName) -> ReplyOut:
    messages = [
        {"role": "system", "content": REPLY_PROMPT},
        {"role": "user", "content": f"Ticket {ticket.ticket_id} from {ticket.employee}:\n{ticket.text}"},
    ]
    try:
        response = llm.chat.completions.create(model=model, messages=messages)
    except openai.OpenAIError as error:
        raise upstream_error(error) from error
    text = response.choices[0].message.content or ""
    return ReplyOut(ticket_id=ticket.ticket_id, reply=text, model=model, usage=usage_of(response))


@app.post("/triage", response_model=TriageOut, tags=["assistant"])
def triage(ticket: TicketIn, llm: LLM, model: ModelName) -> TriageOut:
    messages = [
        {"role": "system", "content": TRIAGE_PROMPT},
        {"role": "user", "content": f"<ticket id=\"{ticket.ticket_id}\" from=\"{ticket.employee}\">\n{ticket.text}\n</ticket>"},
    ]
    try:
        response = llm.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "triage", "schema": Triage.model_json_schema(), "strict": True},
            },
            temperature=0,
        )
    except openai.OpenAIError as error:
        raise upstream_error(error) from error
    raw = response.choices[0].message.content or ""
    try:
        result = Triage.model_validate_json(raw)
    except ValidationError as error:
        # The model broke the contract. Our caller gets a clear 502, never a half-valid object.
        raise HTTPException(
            status_code=502,
            detail={"problem": "model reply did not match the Triage schema", "errors": json.loads(error.json())[:3], "raw": raw[:300]},
        ) from error
    return TriageOut(ticket_id=ticket.ticket_id, triage=result, usage=usage_of(response))
