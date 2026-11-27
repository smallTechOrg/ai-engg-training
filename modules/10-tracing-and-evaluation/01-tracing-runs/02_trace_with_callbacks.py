"""10.1/2  The same trace, collected by a LangChain callback handler

Script 1 wrapped every step in a `with tracer.span(...)` by hand. LangChain already
announces every chain and model call start and end to *callback handlers*, so a handler
can record the same tree with no change to the chain. That is exactly the hook LangSmith
uses to collect traces.

Run it:   ./run 10.1/2          (Windows: run 10.1/2)
"""

import os
import time

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from labkit import lesson

TICKET = (
    "Since this morning the VPN disconnects every ten minutes when I work from home. "
    "I have to log in again each time and it kills my video calls. - Jonas (Engineering)"
)
CATEGORIES = ["network", "hardware", "software", "access", "other"]

PRICE_IN_PER_MILLION = 0.10  # invented example prices, US dollars per million tokens
PRICE_OUT_PER_MILLION = 0.40


class TraceRecorder(BaseCallbackHandler):
    """Records a span for every chain and model call LangChain runs, linked by parent_run_id.

    LangChain calls these methods for you; they are the hooks LangSmith itself uses.
    """

    def __init__(self):
        self.spans = {}  # run_id -> span dict, in start order

    def _start(self, run_id, parent_run_id, name, kind, inputs):
        self.spans[run_id] = {
            "id": run_id, "parent_id": parent_run_id, "name": name, "kind": kind, "inputs": inputs,
            "outputs": None, "tokens_in": 0, "tokens_out": 0, "error": None,
            "start": time.perf_counter(), "end": None,
        }

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        name = kwargs.get("name") or (serialized or {}).get("name") or "chain"
        self._start(run_id, parent_run_id, name, "chain", inputs)

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        self.spans[run_id]["outputs"], self.spans[run_id]["end"] = outputs, time.perf_counter()

    def on_chat_model_start(self, serialized, messages, *, run_id, parent_run_id=None, **kwargs):
        shown = [{"role": m.type, "content": m.content} for m in messages[0]]
        self._start(run_id, parent_run_id, kwargs.get("name") or "ChatOpenAI", "llm", shown)

    def on_llm_end(self, response, *, run_id, **kwargs):
        span = self.spans[run_id]
        message = response.generations[0][0].message
        usage = getattr(message, "usage_metadata", None) or {}
        span["tokens_in"], span["tokens_out"] = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
        span["outputs"], span["end"] = message.content, time.perf_counter()

    def _error(self, error, run_id):
        span = self.spans[run_id]
        span["error"], span["end"] = f"{type(error).__name__}: {error}", time.perf_counter()

    def on_chain_error(self, error, *, run_id, **kwargs):
        self._error(error, run_id)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._error(error, run_id)

    # ---- reading the recording ----
    def seconds(self, span):
        return (span["end"] or time.perf_counter()) - span["start"]

    def own_cost(self, span):
        return (span["tokens_in"] * PRICE_IN_PER_MILLION + span["tokens_out"] * PRICE_OUT_PER_MILLION) / 1_000_000

    def total_tokens(self, span):
        tokens_in, tokens_out = span["tokens_in"], span["tokens_out"]
        for child in self.spans.values():
            if child["parent_id"] == span["id"]:
                child_in, child_out = self.total_tokens(child)
                tokens_in, tokens_out = tokens_in + child_in, tokens_out + child_out
        return tokens_in, tokens_out

    def print_tree(self, ctx, parent_id=None, prefix=""):
        children = [s for s in self.spans.values() if s["parent_id"] == parent_id]
        for index, span in enumerate(children):
            last = index == len(children) - 1
            tokens_in, tokens_out = self.total_tokens(span)
            cost = (tokens_in * PRICE_IN_PER_MILLION + tokens_out * PRICE_OUT_PER_MILLION) / 1_000_000
            label = f"{prefix}{'`- ' if last else '|- '}{span['kind']:<5} {span['name']}"
            flag = "  ERROR" if span["error"] else ""
            ctx.note(f"{label:<40} {self.seconds(span):6.2f}s {tokens_in:>5} in {tokens_out:>5} out  ${cost:.6f}{flag}")
            self.print_tree(ctx, span["id"], prefix + ("   " if last else "|  "))


def build_chain(ctx):
    llm = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    classify = (
        ChatPromptTemplate.from_messages([
            ("system", "Classify the IT helpdesk ticket. Answer with exactly one word from: " + ", ".join(CATEGORIES) + "."),
            ("human", "{ticket}"),
        ])
        | llm
        | StrOutputParser()
    ).with_config(run_name="classify")
    reply = (
        ChatPromptTemplate.from_messages([
            ("system", "You are the Larkspur Labs IT helpdesk. The ticket is a {category} problem. Reply to the employee in at most three short sentences."),
            ("human", "{ticket}"),
        ])
        | llm
        | StrOutputParser()
    ).with_config(run_name="reply")

    def run_both(inputs, config):
        # `config` carries the callbacks down, so the two inner chains become children of this span.
        raw = classify.invoke({"ticket": inputs["ticket"]}, config)
        category = next((c for c in CATEGORIES if c in raw.strip().lower()), "other")
        return {"category": category, "reply": reply.invoke({"ticket": inputs["ticket"], "category": category}, config)}

    return RunnableLambda(run_both).with_config(run_name="helpdesk_reply")


@lesson("10.1/2", "Tracing with a LangChain callback handler")
def main(ctx):
    ctx.step("Build the chain (nothing in it knows about tracing)")
    chain = build_chain(ctx)
    ctx.note("helpdesk_reply = classify (prompt | model | parser), then reply (prompt | model | parser).")

    ctx.step("Run it with the recorder attached")
    recorder = TraceRecorder()
    result = chain.invoke({"ticket": TICKET}, config={"callbacks": [recorder]})
    ctx.show_messages([{"role": "assistant", "content": result["reply"]}], label=f"Reply (category: {result['category']})")
    for span in recorder.spans.values():
        if span["kind"] == "llm" and span["tokens_in"]:
            ctx.record_usage({"input_tokens": span["tokens_in"], "output_tokens": span["tokens_out"]}, quiet=True)

    ctx.step("Print the trace as a tree")
    ctx.note(f"{len(recorder.spans)} spans recorded. Cost uses invented prices: ${PRICE_IN_PER_MILLION}/M in, ${PRICE_OUT_PER_MILLION}/M out.")
    recorder.print_tree(ctx)
    if any(s["kind"] == "llm" and not s["tokens_in"] for s in recorder.spans.values()):
        ctx.note("Some model calls reported no usage, so their tokens count as 0 here.")

    ctx.step("One span as the handler stored it")
    first_llm = next(s for s in recorder.spans.values() if s["kind"] == "llm")
    shown = {k: (str(v) if k in ("id", "parent_id") else v) for k, v in first_llm.items() if k not in ("start", "end")}
    shown["seconds"] = round(recorder.seconds(first_llm), 3)
    ctx.show_data("The first model call", shown)
    ctx.note("Same fields as script 1: name, kind, inputs, outputs, tokens, parent link, timing.")


if __name__ == "__main__":
    main()
