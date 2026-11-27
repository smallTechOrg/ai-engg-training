"""Tiny Larkspur Labs helpdesk API, the thing we put in a container.

Settings come from environment variables (never baked into the image):
LLM_BASE_URL, LLM_API_KEY, LLM_MODEL.
"""

import os

from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI(title="Larkspur Labs helpdesk API")

SYSTEM_PROMPT = "You are the IT helpdesk assistant at Larkspur Labs. Answer in two sentences."


class Question(BaseModel):
    question: str


def _client() -> OpenAI:
    return OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"])


@app.get("/health")
def health() -> dict:
    # Liveness only: no model call, so a slow provider never makes the container "unhealthy".
    return {"status": "ok"}


@app.post("/reply")
def reply(body: Question) -> dict:
    try:
        client = _client()
        done = client.chat.completions.create(
            model=os.environ["LLM_MODEL"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": body.question},
            ],
        )
    except KeyError as missing:
        raise HTTPException(status_code=500, detail=f"missing setting {missing}") from None
    except Exception as exc:  # report, do not crash the worker
        raise HTTPException(status_code=502, detail=f"model call failed: {type(exc).__name__}") from None
    return {"reply": done.choices[0].message.content}
