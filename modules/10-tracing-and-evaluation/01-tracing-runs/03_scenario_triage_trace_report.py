"""10.1/3  Scenario: trace the helpdesk triage and reply chain, find the slow and costly span

The chain classifies three tickets and writes a reply for each. The recorder from
script 2 collects every span; we then ask the two questions tracing exists to answer:
which span was slowest, and which one cost the most?

If LANGSMITH_API_KEY is set in your environment (or .env loaded into it), the same run
is also sent to LangSmith. Without it, nothing changes and nothing fails.

Run it:   ./run 10.1/3          (Windows: run 10.1/3)
"""

import os
import time

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from labkit import lesson

TICKETS = [
    (
        "Since this morning the VPN disconnects every ten minutes when I work from home. "
        "I have to log in again each time and it kills my video calls. - Jonas (Engineering)"
    ),
    "My laptop battery looks swollen and the trackpad is lifting. - Priya (Finance)",
    "I need access to the shared design drive. My manager approved it yesterday. - Tomas (Design)",
]
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


def langsmith_callbacks(ctx):
    """Return a LangSmith tracer if a key is configured, else an empty list. Never raises."""
    if not os.environ.get("LANGSMITH_API_KEY"):
        ctx.note("LangSmith is off: LANGSMITH_API_KEY is not set. To send this run there too, set")
        ctx.note("  LANGSMITH_API_KEY=<your key>   LANGSMITH_TRACING=true   LANGSMITH_PROJECT=larkspur-training")
        ctx.note("in your environment and run again. The local report below works either way.")
        return []
    try:
        from langchain_core.tracers.langchain import LangChainTracer

        project = os.environ.get("LANGSMITH_PROJECT", "larkspur-training")
        ctx.note(f"LangSmith is on: this run is also sent to project '{project}'.")
        return [LangChainTracer(project_name=project)]
    except Exception as exc:  # tracing must never break the app it observes
        ctx.note(f"LangSmith could not be started ({type(exc).__name__}); continuing without it.")
        return []


@lesson("10.1/3", "Scenario: trace triage + reply, find the slowest and costliest span")
def main(ctx):
    ctx.step("Decide where traces go")
    callbacks = [recorder := TraceRecorder()] + langsmith_callbacks(ctx)

    ctx.step("Run the chain on three tickets")
    chain = build_chain(ctx)
    for ticket in TICKETS:
        result = chain.invoke({"ticket": ticket}, config={"callbacks": callbacks})
        ctx.note(f"{ticket[:45]!r:<50} -> {result['category']}: {result['reply'][:70]!r}")
    for span in recorder.spans.values():
        if span["kind"] == "llm" and span["tokens_in"]:
            ctx.record_usage({"input_tokens": span["tokens_in"], "output_tokens": span["tokens_out"]}, quiet=True)

    ctx.step("The trace")
    recorder.print_tree(ctx)

    ctx.step("Slowest and most expensive spans")
    llm_spans = [s for s in recorder.spans.values() if s["kind"] == "llm"]
    slowest = max(llm_spans, key=recorder.seconds)
    costliest = max(llm_spans, key=recorder.own_cost)
    parent = recorder.spans.get(slowest["parent_id"])
    ctx.note(f"Slowest model call:    {recorder.seconds(slowest):.2f}s inside '{parent['name'] if parent else '?'}'")
    ctx.note(f"Most expensive call:   ${recorder.own_cost(costliest):.6f} ({costliest['tokens_in']} in, {costliest['tokens_out']} out)")
    by_name = {}
    for span in llm_spans:
        parent = recorder.spans.get(span["parent_id"])
        key = parent["name"] if parent else span["name"]
        seconds, cost = by_name.get(key, (0.0, 0.0))
        by_name[key] = (seconds + recorder.seconds(span), cost + recorder.own_cost(span))
    ctx.show_data("Per step, summed over the three tickets", {k: {"seconds": round(v[0], 2), "usd": round(v[1], 6)} for k, v in by_name.items()})
    if all(s["tokens_in"] == 0 for s in llm_spans):
        ctx.note("This endpoint reported no token usage, so every cost is $0 here; latency still works.")
    ctx.note("Cost follows output tokens, so the reply step costs most; latency has a fixed network part, so even a one-word classify can be slow.")


if __name__ == "__main__":
    main()
