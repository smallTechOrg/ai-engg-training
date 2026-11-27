"""15.5/2  Capstone, part 2: the agentic pipeline (the reference solution)

Plain RAG's three silent failures from 15.1 get one answer each:

  stale context      -> metadata filter (superseded documents are never indexed);
  missed retrieval   -> grade the chunks, rewrite the query once, retrieve again;
  irrelevant context -> if nothing passes the grade, DECLINE without asking the model to guess.

Every model call is capped (one grade call, at most one rewrite, one answer, per question) and every step is
traced. The same scoring rule as 15.5/1 is applied, so the scores are comparable.

Run it:   ./run 15.5/2          (Windows: run 15.5/2)
"""

import json
import math
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson

HERE = Path(__file__).parent
TOP_K = 2
DECLINE = re.compile(r"do(?:es)? not know|don't know|not (?:in|contain|provid|mention|specif|cover)|no information|cannot (?:find|answer)|unable to (?:find|answer)", re.I)
DECLINE_TEXT = "I do not know. I could not find this in the knowledge base."

ANSWER_PROMPT = """You are the IT helpdesk assistant at Larkspur Labs.
Answer using ONLY the context below. If the context does not contain the answer, say you do not know.
Keep the answer to two sentences."""

GRADE_PROMPT = """You grade search results for a helpdesk assistant.
For each numbered passage decide: does it state the specific fact the question asks for (the number, name or step),
not merely the same topic? A passage that only points elsewhere is relevant=false.
Reply with JSON only: {"grades": [{"number": 1, "relevant": true}, ...]} with one entry per passage."""

REWRITE_PROMPT = """The search below found nothing useful. Write ONE better search query for a knowledge base:
use the words a policy document would use (nouns and numbers, no filler), under 12 words. Reply with the query text only."""


class Grade(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: int
    relevant: bool


class Grades(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grades: list[Grade]


def load_chunks():
    chunks = []
    for path in sorted((HERE / "kb").glob("*.md")):
        header, _, body = path.read_text(encoding="utf-8").partition("\n\n")
        meta = dict(line.split(": ", 1) for line in header.splitlines())
        if meta["status"].startswith("superseded"):
            continue  # fix for stale context
        for position, paragraph in enumerate(p.strip() for p in body.split("\n\n") if p.strip()):
            chunks.append({"id": f"{meta['id']}#{position}", "text": paragraph})
    return chunks


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def passes(item, answer):
    text = answer.lower()
    if not item["answerable"]:
        return bool(DECLINE.search(answer))
    return any(k.lower() in text for k in item["any_of"]) and not any(k.lower() in text for k in item["none_of"])


@lesson("15.5/2", "Capstone: the agentic pipeline")
def main(ctx):
    test_set = json.loads((HERE / "testset.json").read_text(encoding="utf-8"))
    chunks = load_chunks()
    vectors = ctx.embed([c["text"] for c in chunks])
    ctx.note(f"{len(chunks)} current chunks indexed (superseded documents left out).")
    stats = {"calls": 0}

    def chat(messages, **kwargs):
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, **kwargs)
        ctx.record_usage(response.usage, quiet=True)
        stats["calls"] += 1
        return response.choices[0].message.content or ""

    def retrieve(query):
        qv = ctx.embed([query])[0]
        return [c for _, c in sorted(zip(vectors, chunks), key=lambda pair: cosine(qv, pair[0]), reverse=True)[:TOP_K]]

    def grade(question, found):
        listing = "\n\n".join(f"Passage {n}: {c['text']}" for n, c in enumerate(found, start=1))
        reply = chat([{"role": "system", "content": GRADE_PROMPT},
                      {"role": "user", "content": f"Question: {question}\n\n{listing}"}],
                     response_format={"type": "json_object"})
        try:
            marks = {g.number: g.relevant for g in Grades.model_validate_json(reply).grades}
        except (ValidationError, ValueError):
            return list(found)  # unreadable grader: keep everything rather than crash
        return [c for n, c in enumerate(found, start=1) if marks.get(n)]

    def agentic(question):
        trace, query, kept = [], question, []
        for attempt in (1, 2):  # hard cap: one rewrite
            found = retrieve(query)
            kept = grade(question, found)
            trace.append(f"try {attempt}: {[c['id'] for c in found]} -> kept {[c['id'] for c in kept]}")
            if kept or attempt == 2:
                break
            query = chat([{"role": "system", "content": REWRITE_PROMPT},
                          {"role": "user", "content": f"Question: {question}\nFailed search: {query}"}]).strip().strip('"')[:200]
            trace.append(f"rewrite -> {query!r}")
        if not kept:
            trace.append("decline without calling the model")
            return DECLINE_TEXT, trace
        context = "\n\n".join(f"[{c['id']}] {c['text']}" for c in kept)
        return chat([{"role": "system", "content": ANSWER_PROMPT + "\n\nContext:\n" + context},
                     {"role": "user", "content": question}]), trace

    ctx.step("Run the pipeline on the test set")
    passed = 0
    for n, item in enumerate(test_set, start=1):
        answer, trace = agentic(item["question"])
        ok = passes(item, answer)
        passed += ok
        ctx.note(f"Q{n} {'PASS' if ok else 'FAIL'}  {item['question'][:60]}")
        for line in trace:
            ctx.note("      " + line)
        ctx.note(f"      {answer[:150]}")

    ctx.step("Score")
    ctx.note(f"Agentic pipeline: {passed}/{len(test_set)} passed, {stats['calls']} model calls ({stats['calls'] / len(test_set):.1f} per question).")
    ctx.note("Compare with 15.5/1. The extra calls bought the pass-rate difference above, and nothing else.")


if __name__ == "__main__":
    main()
