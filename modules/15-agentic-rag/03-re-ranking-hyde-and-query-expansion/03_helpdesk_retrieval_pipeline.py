"""15.3/3  Scenario: one helpdesk retrieval pipeline with every stage switchable

Combines the lesson's pieces into a pipeline and answers real questions with it:

  rewrite (one LLM call: 3 paraphrases)  ->  embed + RRF merge  ->  cross-encoder re-rank  ->  top 2  ->  answer

Each stage can be switched off, so you can see what it buys. The cross-encoder is optional: if it cannot be
loaded (no network on first run), the pipeline skips that stage and says so.

Run it:   ./run 15.3/3          (Windows: run 15.3/3)
"""

import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
CROSS_ENCODER = "Xenova/ms-marco-MiniLM-L-6-v2"
RRF_K = 60
CANDIDATES = 6
TOP_K = 2

QUESTIONS = [
    "Can I expense a standing desk for my home?",
    "My work machine is three years old. When do I get a new one?",
    "Which program do I install to connect remotely?",
]

ANSWER_PROMPT = """You are the IT helpdesk assistant at Larkspur Labs.
Answer using ONLY the context below; if it does not contain the answer say you do not know.
Keep the answer to two sentences."""

EXPAND_PROMPT = """Write exactly 3 different search queries (different vocabulary each) for the same need, for a
Larkspur Labs IT knowledge base. Reply with JSON only: {"queries": ["...", "...", "..."]}"""


class Queries(BaseModel):
    model_config = ConfigDict(extra="forbid")
    queries: list[str]


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
    return dot / norm if norm else 0.0


@lesson("15.3/3", "A helpdesk retrieval pipeline: expand, fuse, re-rank")
def main(ctx):
    chunks = load_chunks()
    by_id = {c["id"]: c for c in chunks}
    vectors = ctx.embed([c["text"] for c in chunks])
    reranker = None
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        reranker = TextCrossEncoder(CROSS_ENCODER)
    except Exception as exc:
        ctx.note(f"Cross-encoder unavailable ({type(exc).__name__}); the re-rank stage will be skipped.")

    def rank(text):
        qv = ctx.embed([text])[0]
        return [chunks[i]["id"] for i in sorted(range(len(chunks)), key=lambda i: cosine(qv, vectors[i]), reverse=True)]

    def expand(question):
        response = ctx.client.chat.completions.create(
            model=ctx.model, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": EXPAND_PROMPT}, {"role": "user", "content": question}])
        ctx.record_usage(response.usage, quiet=True)
        try:
            return [q for q in Queries.model_validate_json(response.choices[0].message.content or "").queries if q.strip()][:3]
        except (ValidationError, ValueError):
            return []

    def retrieve(question, use_expansion, use_rerank):
        trace = []
        rankings = [rank(question)]
        if use_expansion:
            paraphrases = expand(question)
            trace.append(f"paraphrases: {paraphrases}")
            rankings += [rank(p) for p in paraphrases]
        scores = {}
        for ranking in rankings:
            for position, cid in enumerate(ranking, start=1):
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + position)
        fused = sorted(scores, key=scores.get, reverse=True)[:CANDIDATES]
        trace.append(f"after fusion: {fused}")
        if use_rerank and reranker is not None:
            order = list(reranker.rerank(question, [by_id[c]["text"] for c in fused]))
            fused = [c for _, c in sorted(zip(order, fused), key=lambda pair: pair[0], reverse=True)]
            trace.append(f"after re-rank: {fused}")
        return fused[:TOP_K], trace

    configs = {"plain": (False, False), "expand + fuse": (True, False), "expand + fuse + re-rank": (True, True)}
    for question in QUESTIONS:
        ctx.step("Question: " + question)
        for label, (use_expansion, use_rerank) in configs.items():
            top, trace = retrieve(question, use_expansion, use_rerank)
            ctx.note(f"[{label}] top {TOP_K}: {top}")
            if label == "expand + fuse + re-rank":
                for line in trace:
                    ctx.note("    " + line)
        context = "\n\n".join(f"[{c}] {by_id[c]['text']}" for c in top)
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": ANSWER_PROMPT + "\n\nContext:\n" + context},
                      {"role": "user", "content": question}])
        ctx.show_response(response)

    ctx.step("What to take away")
    ctx.note("Each stage is a trade: expansion adds one model call before retrieval, re-ranking adds CPU")
    ctx.note("time per candidate. Run script 1 and 2's measurements on your own questions before keeping either.")


if __name__ == "__main__":
    main()
