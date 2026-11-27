"""Helpdesk API: accepts a ticket, queues it, and answers 202 at once. The worker does the model call."""

import os
import urllib.request
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.jobs import make_queue

app = FastAPI(title="Larkspur Labs helpdesk API")
jobs = make_queue()


class Ticket(BaseModel):
    text: str


def chroma_ok() -> bool:
    url = os.environ.get("CHROMA_URL", "").strip()
    if not url:
        return True  # not configured: nothing to wait for
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/v2/heartbeat", timeout=2):
            return True
    except Exception:
        return False


@app.get("/health/live")
def live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict:
    checks = {}
    try:
        checks["redis"] = jobs.ping()
    except Exception:
        checks["redis"] = False
    checks["chroma"] = chroma_ok()
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ready", "checks": checks}


@app.post("/tickets", status_code=202)
def submit(ticket: Ticket) -> dict:
    job_id = uuid.uuid4().hex[:12]
    jobs.push({"id": job_id, "text": ticket.text})
    return {"job_id": job_id, "status": "queued"}


@app.get("/tickets/{job_id}")
def status(job_id: str) -> dict:
    result = jobs.get_result(job_id)
    return result or {"job_id": job_id, "status": "queued"}
