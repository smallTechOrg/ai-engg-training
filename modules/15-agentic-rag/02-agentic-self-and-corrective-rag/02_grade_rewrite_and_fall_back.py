"""15.2/2  Corrective RAG by hand: grade what came back, rewrite, then fall back

The corrective-RAG idea (CRAG) puts a checkpoint between retrieval and generation:

  1. RETRIEVE with the question;
  2. GRADE every chunk: is it relevant to the question? (one batched model call);
  3. if nothing is relevant: REWRITE the query and retrieve again (once);
  4. if still nothing: FALL BACK to a different source. Here that is `web_search_stub`, a local
     function with three canned results. There is no internet access in this course.
  5. ANSWER only from chunks that passed the check, or say "I do not know".

Run it:   ./run 15.2/2          (Windows: run 15.2/2)
"""

import json
import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
TOP_K = 2

QUESTIONS = [
    "How long does a VPN session last?",                        # retrieval is fine: grade, answer
    "How much can I spend on a standing desk through the home office stipend?",  # first search misses the amount
    "Which operating systems does the Larkspur Connect VPN client support?",    # not in the KB: web fallback
]

ANSWER_PROMPT = """You are the IT helpdesk assistant at Larkspur Labs.
Answer using ONLY the sources below. If they do not contain the answer, say you do not know.
Keep the answer to two sentences, and name the source id you used in square brackets."""

GRADE_PROMPT = """You grade search results for a helpdesk assistant.
For each numbered passage decide: does it contain information that helps answer the question?
Mark relevant=true only if the passage states the specific fact the question asks for (the number,
name or step), not merely the same topic. A passage that only points elsewhere is relevant=false.
Reply with JSON only: {"grades": [{"number": 1, "relevant": true}, ...]} with one entry per passage."""

REWRITE_PROMPT = """The search below found nothing useful. Write ONE better search query for a knowledge base:
use the words a policy document would use (nouns and numbers, no filler), keep it under 12 words.
Reply with the query text only."""

# A stand-in for a real web search tool. Real tools need the internet and an API key.
WEB_STUB = {
    "operating systems": ("web-1", "Larkspur Connect release notes (stub result): the client supports Windows 11, macOS 14 and later, and Ubuntu 22.04."),
    "printer": ("web-2", "Print servers guide (stub result): printers are installed from the software portal."),
}


class Grade(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: int
    relevant: bool


class Grades(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grades: list[Grade]


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


def web_search_stub(query):
    """Canned results: matches when a key phrase appears in the query, else no results."""
    q = query.lower()
    return [{"id": i, "text": t} for key, (i, t) in WEB_STUB.items() if key in q or all(w in q for w in key.split())]


@lesson("15.2/2", "Grade, rewrite and fall back (corrective RAG)")
def main(ctx):
    chunks = load_chunks()
    vectors = ctx.embed([c["text"] for c in chunks])

    def retrieve(query):
        qv = ctx.embed([query])[0]
        ranked = sorted(zip(vectors, chunks), key=lambda pair: cosine(qv, pair[0]), reverse=True)
        return [c for _, c in ranked[:TOP_K]]

    def chat(messages, **kwargs):
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, **kwargs)
        ctx.record_usage(response.usage, quiet=True)
        return response.choices[0].message.content or ""

    def grade(question, found):
        """One call grades all passages. An unreadable reply counts as 'all relevant' so the run goes on."""
        listing = "\n\n".join(f"Passage {n}: {c['text']}" for n, c in enumerate(found, start=1))
        reply = chat([{"role": "system", "content": GRADE_PROMPT},
                      {"role": "user", "content": f"Question: {question}\n\n{listing}"}],
                     response_format={"type": "json_object"})
        try:
            marks = {g.number: g.relevant for g in Grades.model_validate_json(reply).grades}
        except (ValidationError, ValueError):
            ctx.note("  The grader's reply was not valid JSON; treating every passage as relevant.")
            return list(found)
        return [c for n, c in enumerate(found, start=1) if marks.get(n, False)]

    model_calls = 0
    for question in QUESTIONS:
        ctx.step("Question: " + question)
        route, kept, query = "vector search", [], question
        for attempt in (1, 2):
            found = retrieve(query)
            ctx.note(f"Attempt {attempt}: query = {query!r}")
            ctx.note("  retrieved: " + ", ".join(c["id"] for c in found))
            kept = grade(question, found)
            model_calls += 1
            ctx.note("  graded relevant: " + (", ".join(c["id"] for c in kept) or "none"))
            if kept or attempt == 2:
                break
            query = chat([{"role": "system", "content": REWRITE_PROMPT},
                          {"role": "user", "content": f"Question: {question}\nFailed search: {query}"}]).strip().strip('"')[:200]
            model_calls += 1
        if not kept:
            ctx.note("Still nothing relevant. Falling back to the web search stub.")
            results = web_search_stub(question + " " + query)
            ctx.show_tool_call("web_search_stub", {"query": query}, results or "no results")
            kept, route = results, "web search stub"
        if not kept:
            ctx.note("No source survived the checks, so we do not call the model to guess.")
            ctx.note("assistant | I do not know. I could not find this in the knowledge base or on the web.")
            continue
        context = "\n\n".join(f"[{c['id']}] {c['text']}" for c in kept)
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": ANSWER_PROMPT + "\n\nSources (" + route + "):\n" + context},
                      {"role": "user", "content": question}])
        model_calls += 1
        ctx.show_response(response)

    ctx.step("What to take away")
    ctx.note(f"Model calls in this script: {model_calls}. Plain RAG would have used 3, one per question.")
    ctx.note("The grader is the new moving part: it can be too strict (drops a chunk that mattered) or")
    ctx.note("too lenient (keeps a topical but useless one). Always read its verdicts, as above.")


if __name__ == "__main__":
    main()
