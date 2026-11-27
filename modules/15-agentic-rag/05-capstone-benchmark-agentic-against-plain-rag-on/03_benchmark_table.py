"""15.5/3  Capstone, part 3: the benchmark table

Three systems, one test set, one scoring rule, side by side:

  A. plain RAG over every document (the 15.5/1 baseline);
  B. plain RAG over current documents only (the 15.1 metadata fix, free);
  C. the agentic pipeline of 15.5/2 (grade, rewrite once, decline).

For each: questions passed, model calls, tokens and wall-clock time. The point of a benchmark is the cost
column next to the quality column. With six questions a single flipped answer moves a score by 17 points,
so run it twice before believing a one-question difference.

Run it:   ./run 15.5/3          (Windows: run 15.5/3)
"""

import json
import math
import re
import time
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


def load_chunks(current_only):
    chunks = []
    for path in sorted((HERE / "kb").glob("*.md")):
        header, _, body = path.read_text(encoding="utf-8").partition("\n\n")
        meta = dict(line.split(": ", 1) for line in header.splitlines())
        if current_only and meta["status"].startswith("superseded"):
            continue
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


@lesson("15.5/3", "Capstone: benchmark plain against agentic RAG")
def main(ctx):
    test_set = json.loads((HERE / "testset.json").read_text(encoding="utf-8"))
    corpora = {}
    for current_only in (False, True):
        chunks = load_chunks(current_only)
        corpora[current_only] = (chunks, ctx.embed([c["text"] for c in chunks]))
    meter = {"calls": 0, "tokens": 0}

    def chat(messages, **kwargs):
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, **kwargs)
        ctx.record_usage(response.usage, quiet=True)
        meter["calls"] += 1
        meter["tokens"] += getattr(response.usage, "total_tokens", 0) or 0
        return response.choices[0].message.content or ""

    def retrieve(query, current_only):
        chunks, vectors = corpora[current_only]
        qv = ctx.embed([query])[0]
        return [c for _, c in sorted(zip(vectors, chunks), key=lambda pair: cosine(qv, pair[0]), reverse=True)[:TOP_K]]

    def answer_from(question, found):
        context = "\n\n".join(f"[{c['id']}] {c['text']}" for c in found)
        return chat([{"role": "system", "content": ANSWER_PROMPT + "\n\nContext:\n" + context},
                     {"role": "user", "content": question}])

    def plain(current_only):
        return lambda question: answer_from(question, retrieve(question, current_only))

    def grade(question, found):
        listing = "\n\n".join(f"Passage {n}: {c['text']}" for n, c in enumerate(found, start=1))
        reply = chat([{"role": "system", "content": GRADE_PROMPT},
                      {"role": "user", "content": f"Question: {question}\n\n{listing}"}],
                     response_format={"type": "json_object"})
        try:
            marks = {g.number: g.relevant for g in Grades.model_validate_json(reply).grades}
        except (ValidationError, ValueError):
            return list(found)
        return [c for n, c in enumerate(found, start=1) if marks.get(n)]

    def agentic(question):
        query, kept = question, []
        for attempt in (1, 2):
            kept = grade(question, retrieve(query, True))
            if kept or attempt == 2:
                break
            query = chat([{"role": "system", "content": REWRITE_PROMPT},
                          {"role": "user", "content": f"Question: {question}\nFailed search: {query}"}]).strip().strip('"')[:200]
        return answer_from(question, kept) if kept else DECLINE_TEXT

    systems = {"A plain, all documents": plain(False), "B plain, current documents": plain(True), "C agentic": agentic}
    rows, failures = [], {}
    for name, system in systems.items():
        ctx.step("Running " + name)
        meter["calls"] = meter["tokens"] = 0
        started, passed = time.monotonic(), 0
        for n, item in enumerate(test_set, start=1):
            answer = system(item["question"])
            ok = passes(item, answer)
            passed += ok
            if not ok:
                failures.setdefault(name, []).append(f"Q{n}: {answer[:110]}")
        rows.append((name, passed, meter["calls"], meter["tokens"], time.monotonic() - started))
        ctx.note(f"{passed}/{len(test_set)} passed")

    ctx.step("The benchmark table")
    ctx.note(f"{'system':<28}{'passed':>8}{'calls':>7}{'tokens':>8}{'seconds':>9}")
    for name, passed, calls, tokens, seconds in rows:
        ctx.note(f"{name:<28}{f'{passed}/{len(test_set)}':>8}{calls:>7}{tokens or 'n/a':>8}{seconds:>9.1f}")
    ctx.step("What failed")
    for name, lines in failures.items():
        ctx.note(name)
        for line in lines:
            ctx.note("   " + line)
    if not failures:
        ctx.note("Nothing failed in this run.")
    ctx.note("Quality per cost: agentic RAG buys its extra passes with extra calls. Whether that is worth it")
    ctx.note("depends on how costly a wrong or invented answer is, which is a product decision, not a code one.")


if __name__ == "__main__":
    main()
