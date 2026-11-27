"""15.2/3  Scenario: a LangGraph helpdesk assistant with grading, fallback and a self-check

Lesson 02 wrote the corrective loop as a Python function. Here the same ideas are a LangGraph
state machine, plus one new check borrowed from Self-RAG: after answering, the model checks its OWN
answer against the sources ("is every claim supported?") and the graph regenerates once if not.

  retrieve -> grade -> relevant? -> generate -> self_check -> supported? -> done
                |                                                 '-> generate again (once)
                '-> not relevant: rewrite -> retrieve (once) -> else web -> generate, or decline

Nodes call the model directly with `ctx.client`; LangGraph only owns the wiring and the state.

Run it:   ./run 15.2/3          (Windows: run 15.2/3)
"""

import json
import math
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
TOP_K = 2

QUESTIONS = [
    "How often are laptops replaced?",               # two near-duplicate documents
    "Is the Heron VPN client still supported?",      # the answer changed in 2025
    "Does Larkspur Labs offer pet insurance?",       # nowhere: the graph should decline
]

ANSWER_PROMPT = """You are the IT helpdesk assistant at Larkspur Labs.
Answer using ONLY the sources below. Keep the answer to two sentences and name the source id in square brackets."""

GRADE_PROMPT = """You grade search results for a helpdesk assistant. For each numbered passage decide whether it
states the specific fact the question asks for (not merely the same topic).
Reply with JSON only: {"grades": [{"number": 1, "relevant": true}, ...]} with one entry per passage."""

REWRITE_PROMPT = """The search below found nothing useful. Write ONE better knowledge-base search query using the
words a policy document would use (nouns and numbers, no filler), under 12 words. Reply with the query text only."""

CHECK_PROMPT = """You check an answer against its sources. Is EVERY claim in the answer supported by the sources?
Reply with JSON only: {"supported": true, "problem": ""}  (use supported=false and name the unsupported claim in problem)."""

WEB_STUB = {"operating systems": ("web-1", "Larkspur Connect release notes (stub result): supports Windows 11, macOS 14 and later, and Ubuntu 22.04.")}


class Grades(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grades: list[dict]


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supported: bool
    problem: str = ""


class State(TypedDict):
    question: str
    query: str
    attempts: int
    found: list[dict]
    sources: list[dict]
    route: str
    answer: str
    regenerations: int
    supported: bool
    trace: list[str]


def load_chunks():
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        header, _, body = path.read_text(encoding="utf-8").partition("\n\n")
        meta = dict(line.split(": ", 1) for line in header.splitlines())
        if meta["status"].startswith("superseded"):
            continue
        for position, paragraph in enumerate(p.strip() for p in body.split("\n\n") if p.strip()):
            chunks.append({"id": f"{meta['id']}#{position}", "text": paragraph})
    return chunks


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


@lesson("15.2/3", "A LangGraph assistant with grading, fallback and self-check")
def main(ctx):
    chunks = load_chunks()
    vectors = ctx.embed([c["text"] for c in chunks])
    calls = {"model": 0}

    def chat(messages, **kwargs):
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, **kwargs)
        ctx.record_usage(response.usage, quiet=True)
        calls["model"] += 1
        return response.choices[0].message.content or ""

    # ---- nodes: each takes the state and returns the keys it changes ----
    def retrieve(state: State):
        qv = ctx.embed([state["query"]])[0]
        ranked = sorted(zip(vectors, chunks), key=lambda pair: cosine(qv, pair[0]), reverse=True)
        found = [c for _, c in ranked[:TOP_K]]
        return {"found": found, "attempts": state["attempts"] + 1,
                "trace": state["trace"] + [f"retrieve({state['query']!r}) -> {[c['id'] for c in found]}"]}

    def grade(state: State):
        listing = "\n\n".join(f"Passage {n}: {c['text']}" for n, c in enumerate(state["found"], start=1))
        reply = chat([{"role": "system", "content": GRADE_PROMPT},
                      {"role": "user", "content": f"Question: {state['question']}\n\n{listing}"}],
                     response_format={"type": "json_object"})
        try:
            marks = {int(g["number"]): bool(g["relevant"]) for g in Grades.model_validate_json(reply).grades}
            kept = [c for n, c in enumerate(state["found"], start=1) if marks.get(n)]
        except (ValidationError, ValueError, KeyError, TypeError):
            kept = list(state["found"])  # unreadable grader: keep everything so the run still ends
        return {"sources": kept, "route": "knowledge base",
                "trace": state["trace"] + [f"grade -> kept {[c['id'] for c in kept]}"]}

    def rewrite(state: State):
        query = chat([{"role": "system", "content": REWRITE_PROMPT},
                      {"role": "user", "content": f"Question: {state['question']}\nFailed search: {state['query']}"}]).strip().strip('"')[:200]
        return {"query": query or state["question"], "trace": state["trace"] + [f"rewrite -> {query!r}"]}

    def web(state: State):
        text = (state["question"] + " " + state["query"]).lower()
        results = [{"id": i, "text": t} for key, (i, t) in WEB_STUB.items() if key in text]
        return {"sources": results, "route": "web search stub",
                "trace": state["trace"] + [f"web_search_stub -> {len(results)} result(s)"]}

    def generate(state: State):
        context = "\n\n".join(f"[{c['id']}] {c['text']}" for c in state["sources"])
        extra = "\nBe strict: state nothing that is not in the sources." if state["regenerations"] else ""
        answer = chat([{"role": "system", "content": ANSWER_PROMPT + extra + "\n\nSources:\n" + context},
                       {"role": "user", "content": state["question"]}])
        return {"answer": answer, "trace": state["trace"] + ["generate"]}

    def self_check(state: State):
        context = "\n\n".join(f"[{c['id']}] {c['text']}" for c in state["sources"])
        reply = chat([{"role": "system", "content": CHECK_PROMPT},
                      {"role": "user", "content": f"Sources:\n{context}\n\nAnswer: {state['answer']}"}],
                     response_format={"type": "json_object"})
        try:
            check = Check.model_validate_json(reply)
        except (ValidationError, ValueError):
            check = Check(supported=True, problem="check unreadable, accepted")
        return {"supported": check.supported, "regenerations": state["regenerations"] + (0 if check.supported else 1),
                "trace": state["trace"] + [f"self_check -> supported={check.supported} {check.problem}".strip()]}

    def decline(state: State):
        return {"answer": "I do not know. I could not find this in the knowledge base or on the web.",
                "route": "none", "trace": state["trace"] + ["decline (no model call)"]}

    # ---- edges: plain functions that return the NAME of the next node ----
    def after_grade(state: State):
        if state["sources"]:
            return "generate"
        return "rewrite" if state["attempts"] < 2 else "web"

    def after_web(state: State):
        return "generate" if state["sources"] else "decline"

    def after_check(state: State):
        return END if state["supported"] or state["regenerations"] > 1 else "generate"
        # regenerations counts failed checks: at most 2 failed checks, i.e. one regeneration

    graph = StateGraph(State)
    for name, fn in [("retrieve", retrieve), ("grade", grade), ("rewrite", rewrite), ("web", web),
                     ("generate", generate), ("self_check", self_check), ("decline", decline)]:
        graph.add_node(name, fn)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", after_grade, ["generate", "rewrite", "web"])
    graph.add_edge("rewrite", "retrieve")
    graph.add_conditional_edges("web", after_web, ["generate", "decline"])
    graph.add_edge("generate", "self_check")
    graph.add_conditional_edges("self_check", after_check, ["generate", END])
    graph.add_edge("decline", END)
    app = graph.compile()

    ctx.step("The graph")
    ctx.note("Nodes: " + ", ".join(n for n in app.get_graph().nodes if not n.startswith("__")))

    for question in QUESTIONS:
        ctx.step("Question: " + question)
        before = calls["model"]
        initial: State = {"question": question, "query": question, "attempts": 0, "found": [], "sources": [],
                          "route": "", "answer": "", "regenerations": 0, "supported": False, "trace": []}
        final = app.invoke(initial, config={"recursion_limit": 25})  # a hard stop if an edge ever loops
        for line in final["trace"]:
            ctx.note("  " + line)
        ctx.note(f"  route: {final['route']}   model calls: {calls['model'] - before}")
        ctx.note("assistant | " + final["answer"])

    ctx.step("What to take away")
    ctx.note(f"{calls['model']} model calls in total. Every loop has a cap: one rewrite, one regeneration,")
    ctx.note("and a recursion limit on the whole graph. The graph is the same logic as script 2, but each")
    ctx.note("step is now a named node you can trace, test alone, and rewire without touching the others.")
    ctx.note("Here the model calls come from ctx.client, so the lesson's token total is exact.")


if __name__ == "__main__":
    main()
