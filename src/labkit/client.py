"""Build the OpenAI-compatible client the lessons use.

The client is an ordinary `openai.OpenAI`. The only addition is a pair of HTTP hooks so a
lesson run with `--raw` can show exactly what went over the wire. The HTTP client comes from
the SDK itself (`DefaultHttpxClient`), so this works whichever HTTP library the SDK ships with.
"""

from __future__ import annotations

import json
from typing import Callable

from openai import DefaultHttpxClient, OpenAI

from labkit.config import Settings, load_settings

WireListener = Callable[[str, str, object], None]  # (direction, summary, body)


def _body(raw: bytes) -> object:
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")[:2000]


def get_client(
    settings: Settings | None = None,
    *,
    on_wire: WireListener | None = None,
    embeddings: bool = False,
) -> OpenAI:
    """Return a client for the chat endpoint (or the embeddings endpoint)."""
    settings = (settings or load_settings()).require()
    hooks: dict[str, list] = {}

    if on_wire is not None:

        def on_request(request) -> None:
            on_wire("request", f"{request.method} {request.url}", _body(request.read()))

        def on_response(response) -> None:
            summary = f"{response.status_code} {response.reason_phrase}"
            if "text/event-stream" in response.headers.get("content-type", ""):
                on_wire("response", summary, "(streamed: the chunks are shown as they arrive)")
            else:
                on_wire("response", summary, _body(response.read()))

        hooks = {"request": [on_request], "response": [on_response]}

    return OpenAI(
        base_url=settings.embedding_base_url if embeddings else settings.base_url,
        api_key=settings.embedding_api_key if embeddings else settings.api_key,
        timeout=settings.timeout,
        max_retries=1,
        http_client=DefaultHttpxClient(event_hooks=hooks, timeout=settings.timeout),
    )
