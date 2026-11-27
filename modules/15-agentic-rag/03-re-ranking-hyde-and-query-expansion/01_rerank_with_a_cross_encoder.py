"""15.3/1  Re-ranking: retrieve wide with embeddings, then re-order with a cross-encoder

An embedding model (a "bi-encoder") turns the question and each chunk into vectors separately, so
search is fast but the model never sees question and chunk together. A cross-encoder reads the pair
(question, chunk) at once and outputs one relevance score. It is too slow to run over every chunk,
so the standard recipe is two stages:

  1. recall:    embeddings pick the top 6 candidates cheaply;
  2. precision: a cross-encoder re-orders those 6; the prompt gets the top 2.

The cross-encoder is a small open model that runs on your CPU through fastembed (about 90 MB, downloaded
once). No chat model is needed for this script.

Run it:   ./run 15.3/1          (Windows: run 15.3/1)
"""

import math
from pathlib import Path

from labkit import lesson
from labkit.errors import ServiceUnavailable

KB_DIR = Path(__file__).parent / "kb"
CROSS_ENCODER = "Xenova/ms-marco-MiniLM-L-6-v2"
CANDIDATES = 6
TOP_K = 2

# (question, ids of chunks that contain the answer). Words differ from the documents on purpose.
TEST_SET = [
    ("Can I expense a standing desk for my home?", ["stipend#1"]),
    ("My work machine is three years old. When do I get a new one?", ["laptop-faq#0", "laptop-guide#0"]),
    ("I cannot get into my account and my security key is gone.", ["password#1"]),
    ("Which wireless network should a visitor join?", ["wifi#0"]),
    ("Which program do I install to connect remotely?", ["vpn-2025#2"]),
    ("How long before I am signed out of the VPN?", ["vpn-2025#1"]),
]


def load_chunks():
    """Current documents only (superseded ones are filtered out, the 15.1 fix); one chunk per paragraph."""
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


@lesson("15.3/1", "Re-ranking with a cross-encoder")
def main(ctx):
    ctx.step("Load the two models")
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        reranker = TextCrossEncoder(CROSS_ENCODER)
    except Exception as exc:  # no network on first run, or fastembed without rerankers
        raise ServiceUnavailable(
            f"The cross-encoder {CROSS_ENCODER} could not be loaded ({type(exc).__name__}).",
            ["Run once with internet access so fastembed can download it (about 90 MB).",
             "Install the extra: uv sync --extra rag",
             "Or skip this script: scripts 2 and 3 of this lesson do not need it, except 3's rerank step."]) from exc
    chunks = load_chunks()
    vectors = ctx.embed([c["text"] for c in chunks])
    ctx.note(f"{len(chunks)} chunks. Stage 1 = embeddings ({len(vectors[0])} dims), stage 2 = {CROSS_ENCODER}.")

    hits = {"embeddings only": [0, 0], "embeddings + cross-encoder": [0, 0]}  # [hit@1, hit@2]
    for number, (question, expected) in enumerate(TEST_SET, start=1):
        ctx.step(f"Question {number}: {question}")
        qv = ctx.embed([question])[0]
        ranked = sorted(zip(vectors, chunks), key=lambda pair: cosine(qv, pair[0]), reverse=True)[:CANDIDATES]
        candidates = [(cosine(qv, v), c) for v, c in ranked]
        scores = list(reranker.rerank(question, [c["text"] for _, c in candidates]))
        reordered = sorted(zip(scores, [c for _, c in candidates]), key=lambda pair: pair[0], reverse=True)
        ctx.note(f"  wanted: {expected}")
        ctx.note("  stage 1 (cosine)                       stage 2 (cross-encoder score)")
        for (cos, c1), (score, c2) in zip(candidates, reordered):
            ctx.note(f"  {c1['id']:<16} {cos:.2f}                    {c2['id']:<16} {score:6.2f}")
        for label, order in (("embeddings only", [c for _, c in candidates]),
                             ("embeddings + cross-encoder", [c for _, c in reordered])):
            ids = [c["id"] for c in order]
            hits[label][0] += int(ids[0] in expected)
            hits[label][1] += int(bool(set(ids[:TOP_K]) & set(expected)))

    ctx.step("Result over the test set")
    for label, (at1, at2) in hits.items():
        ctx.note(f"{label:<28} correct chunk ranked first: {at1}/{len(TEST_SET)}   in the top {TOP_K}: {at2}/{len(TEST_SET)}")
    ctx.note("Cross-encoder scores are not probabilities: only their order matters, and they cannot be")
    ctx.note("compared across questions. Cosine scores from 15.1 were also only meaningful relatively.")
    ctx.note("Cost: the cross-encoder ran once per candidate per question. Re-ranking 6 is cheap, 600 is not.")


if __name__ == "__main__":
    main()
