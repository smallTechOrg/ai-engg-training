"""15.3/2  HyDE and query expansion: improve the QUERY instead of the ranking

A question and its answer often use different words ("expense a desk" vs "home office stipend ... 400 USD").
Two tricks bridge that gap by asking a model to rewrite the question before searching:

  * HyDE (Hypothetical Document Embeddings): the model writes a short, plausible ANSWER, and we embed
    that instead of the question. An answer looks more like the document than a question does.
    The answer may be factually wrong; it is only used to find real text, never shown to the user.
  * Multi-query expansion: the model writes three paraphrases; we search with the question and each
    paraphrase and merge the rankings with Reciprocal Rank Fusion (RRF).

One batched model call produces the rewrites for every test question. Retrieval is then free,
so we can measure which variant ranks the right chunk first.

Run it:   ./run 15.3/2          (Windows: run 15.3/2)
"""

import json
import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
RRF_K = 60  # the constant in 1 / (k + rank); 60 is the value from the original RRF paper

TEST_SET = [
    ("Can I expense a standing desk for my home?", ["stipend#1"]),
    ("My work machine is three years old. When do I get a new one?", ["laptop-faq#0", "laptop-guide#0"]),
    ("I cannot get into my account and my security key is gone.", ["password#1"]),
    ("Which wireless network should a visitor join?", ["wifi#0"]),
    ("Which program do I install to connect remotely?", ["vpn-2025#2"]),
    ("How long before I am signed out of the VPN?", ["vpn-2025#1"]),
]

REWRITE_PROMPT = """You help a search system for the Larkspur Labs IT knowledge base (VPN, Wi-Fi, laptops, passwords, home office stipend).
For EACH numbered question write:
  - "hypothetical_answer": two sentences that could appear in a policy document answering it. Invent plausible
    specifics; it will only be used for searching, never shown to anyone.
  - "queries": exactly 3 different search queries for the same need, using different vocabulary each.
Reply with JSON only, in this shape:
{"items": [{"number": 1, "hypothetical_answer": "...", "queries": ["...", "...", "..."]}]}"""


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: int
    hypothetical_answer: str
    queries: list[str]


class Items(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[Item]


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
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0  # an empty text embeds to a zero vector


def rank(vector, chunks, vectors):
    """Chunk ids, best first."""
    order = sorted(range(len(chunks)), key=lambda i: cosine(vector, vectors[i]), reverse=True)
    return [chunks[i]["id"] for i in order]


def rrf(rankings):
    """Reciprocal Rank Fusion: a chunk scores 1/(k+rank) in each list; add them up."""
    scores = {}
    for ranking in rankings:
        for position, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + position)
    return sorted(scores, key=scores.get, reverse=True)


@lesson("15.3/2", "HyDE and query expansion")
def main(ctx):
    ctx.step("Index the knowledge base")
    chunks = load_chunks()
    vectors = ctx.embed([c["text"] for c in chunks])
    ctx.note(f"{len(chunks)} chunks, {len(TEST_SET)} test questions.")

    ctx.step("One batched call writes the rewrites for every question")
    numbered = "\n".join(f"{n}. {q}" for n, (q, _) in enumerate(TEST_SET, start=1))
    messages = [{"role": "system", "content": REWRITE_PROMPT}, {"role": "user", "content": numbered}]
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages,
                                                  response_format={"type": "json_object"})
    ctx.record_usage(response.usage, quiet=True)
    try:
        rewrites = {i.number: i for i in Items.model_validate_json(response.choices[0].message.content or "").items}
    except (ValidationError, ValueError):
        rewrites = {}
        ctx.note("The model did not return usable JSON. Every question falls back to its own words,")
        ctx.note("so the HyDE and multi-query columns below equal the baseline.")
    for n in sorted(rewrites)[:2]:
        ctx.show_data(f"Rewrites for question {n}", rewrites[n].model_dump())

    ctx.step("Retrieve four ways and score each (retrieval only, no model calls)")
    strategies = ["baseline (question)", "HyDE (embed the hypothetical answer)",
                  "multi-query + RRF", "HyDE + multi-query + RRF"]
    score = {s: [0, 0] for s in strategies}  # [correct first, correct in top 2]
    for n, (question, expected) in enumerate(TEST_SET, start=1):
        rw = rewrites.get(n)
        hyde_text = rw.hypothetical_answer if rw and rw.hypothetical_answer.strip() else question
        paraphrases = [q for q in (rw.queries if rw else []) if q.strip()][:3]
        texts = [question, hyde_text] + paraphrases
        qv = dict(zip(texts, ctx.embed(texts)))  # one embedding call per question
        base = rank(qv[question], chunks, vectors)
        hyde = rank(qv[hyde_text], chunks, vectors)
        multi = rrf([base] + [rank(qv[p], chunks, vectors) for p in paraphrases])
        both = rrf([base, hyde] + [rank(qv[p], chunks, vectors) for p in paraphrases])
        row = []
        for strategy, ids in zip(strategies, (base, hyde, multi, both)):
            score[strategy][0] += int(ids[0] in expected)
            score[strategy][1] += int(bool(set(ids[:2]) & set(expected)))
            row.append(ids[0])
        ctx.note(f"Q{n} wanted {expected[0]:<14} first-ranked: " + " | ".join(row))

    ctx.step("Result")
    for strategy, (first, top2) in score.items():
        ctx.note(f"{strategy:<40} first: {first}/{len(TEST_SET)}   in top 2: {top2}/{len(TEST_SET)}")
    ctx.note("Each rewrite costs model latency BEFORE retrieval, and HyDE can mislead when the model")
    ctx.note("invents a confident but wrong answer. Keep a variant only if it wins on YOUR test set.")


if __name__ == "__main__":
    main()
