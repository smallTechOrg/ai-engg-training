"""The helpdesk demo UI in Gradio (lesson 05.4).

Gradio turns a Python FUNCTION into a web UI: you name the inputs and outputs, Gradio builds the
page and an HTTP API for it. Nothing here launches a server at import time. To run it for real,
from the repo root:

    uv run python -c "import sys; sys.path.insert(0, 'modules/05-serving-ai-apps/04-a-demo-ui-in-gradio-choosing-between-the-two'); import gradio_demo; gradio_demo.build_demo().launch()"

The lesson scripts build the UI and call the handler functions directly.
"""

from __future__ import annotations

import json

import gradio as gr

_llm = {"client": None, "model": None}  # a lesson script may set these; otherwise .env is used


def configure(client, model: str) -> None:
    _llm["client"], _llm["model"] = client, model


def client_and_model():
    if _llm["client"] is not None:
        return _llm["client"], _llm["model"]
    from labkit import get_client, load_settings

    settings = load_settings().require()
    return get_client(settings), settings.model


SYSTEM = (
    "You are the first-line IT helpdesk assistant at Larkspur Labs. Answer in at most three short "
    "sentences and give one concrete thing to try first."
)

TRIAGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "category": {"type": "string", "enum": ["network", "hardware", "software", "access", "other"]},
        "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary": {"type": "string"},
        "needs_human": {"type": "boolean"},
    },
    "required": ["category", "urgency", "summary", "needs_human"],
}

usage_log: list = []  # (prompt_tokens, completion_tokens) of every call made by the handlers


def triage_handler(ticket: str, employee: str):
    """Gradio calls this with one value per input component and expects one value per output."""
    client, model = client_and_model()
    if len(ticket.strip()) < 10:
        raise gr.Error("Please describe the problem in at least a sentence.")  # shown as a red toast in the UI
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Triage this Larkspur Labs IT ticket. needs_human is true when a person must act."},
            {"role": "user", "content": f"From {employee or 'unknown'}:\n{ticket}"},
        ],
        response_format={"type": "json_schema", "json_schema": {"name": "triage", "schema": TRIAGE_SCHEMA, "strict": True}},
        temperature=0,
    )
    if response.usage:
        usage_log.append((response.usage.prompt_tokens, response.usage.completion_tokens))
    try:
        data = json.loads(response.choices[0].message.content or "")
    except json.JSONDecodeError:
        raise gr.Error("The model did not return valid JSON; try again.") from None
    return data.get("category", "?"), data.get("urgency", "?"), data


def chat_handler(message: str, history: list):
    """For gr.ChatInterface: `history` is a list of {"role", "content"} dicts; yield the growing reply."""
    client, model = client_and_model()
    messages = [{"role": "system", "content": SYSTEM}] + [{"role": h["role"], "content": h["content"]} for h in history]
    messages.append({"role": "user", "content": message})
    stream = client.chat.completions.create(
        model=model, messages=messages, stream=True, stream_options={"include_usage": True}
    )
    text = ""
    for chunk in stream:
        if chunk.usage:
            usage_log.append((chunk.usage.prompt_tokens, chunk.usage.completion_tokens))
        for choice in chunk.choices or []:
            if choice.delta.content:
                text += choice.delta.content
                yield text  # Gradio replaces the bubble with each yielded string


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Larkspur Labs helpdesk") as demo:
        gr.Markdown("## Larkspur Labs helpdesk demo")
        with gr.Tab("Triage a ticket"):
            employee = gr.Textbox(label="Your name", placeholder="Priya")
            ticket = gr.Textbox(label="Describe the problem", lines=3)
            go = gr.Button("Triage", variant="primary")
            category = gr.Textbox(label="Category")
            urgency = gr.Textbox(label="Urgency")
            raw = gr.JSON(label="Full triage")
            go.click(triage_handler, inputs=[ticket, employee], outputs=[category, urgency, raw], api_name="triage")
        with gr.Tab("Chat"):
            gr.ChatInterface(chat_handler, examples=["My VPN keeps dropping."], api_name="chat")
    return demo
