"""03.4/2  Fuse two rankings with Reciprocal Rank Fusion (RRF)

RRF ignores the scores and uses only the positions: each ranker gives a document
1 / (k + rank), and the sums decide the final order. A document both rankers like wins;
one ranker's strong opinion is not lost. The constant k (60 is the classic default) controls
how much the top positions dominate.

Run it:   ./run 03.4/2          (Windows: run 03.4/2)
Needs the `rag` extra (rank_bm25 + local embedding model). No chat model is used.
"""

import json
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from labkit import lesson

KB = json.loads(Path(__file__).with_name("kb.json").read_text(encoding="utf-8"))
QUERY = "VPN is connected but the wiki and ticket system do not open at home"


# Without a stop-word list, "my", "the" and "on" make BM25 match nearly every article a little.
STOP = {"a", "an", "the", "my", "i", "me", "to", "of", "on", "in", "at", "is", "it", "and", "or", "do", "does",
        "not", "no", "for", "with", "from", "if", "so", "be", "are", "was", "after", "when", "how", "what", "will", "can"}


def tokens(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def rrf(rankings, k=60):
    """rankings: lists of doc indexes, best first. Returns [(doc, fused_score)] best first."""
    fused = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            fused[doc] = fused.get(doc, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda kv: -kv[1])


@lesson("03.4/2", "Reciprocal Rank Fusion")
def main(ctx):
    bm25 = BM25Okapi([tokens(a["text"]) for a in KB])
    vectors = np.array(ctx.embed([a["text"] for a in KB]))
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)

    ctx.step("Two rankings for one query")
    ctx.note(QUERY)
    kw_rank = [int(i) for i in np.argsort(-bm25.get_scores(tokens(QUERY)))]
    q = np.array(ctx.embed([QUERY])[0])
    sem_rank = [int(i) for i in np.argsort(-(vectors @ (q / np.linalg.norm(q))))]
    for r in range(4):
        ctx.note(f"rank {r + 1}:  BM25 {KB[kw_rank[r]]['id']}    vector {KB[sem_rank[r]]['id']}")

    ctx.step("Fuse with RRF (k = 60)")
    fused = rrf([kw_rank, sem_rank], k=60)
    for pos, (doc, score) in enumerate(fused[:4], 1):
        ctx.note(
            f"#{pos} {KB[doc]['id']} fused {score:.4f}  "
            f"(BM25 rank {kw_rank.index(doc) + 1}, vector rank {sem_rank.index(doc) + 1})  {KB[doc]['text'][:50]}"
        )

    ctx.step("The k constant: small k rewards the very top, large k flattens")
    for k in (1, 60, 1000):
        top = rrf([kw_rank, sem_rank], k=k)[:3]
        ctx.note(f"k={k:<4} top 3: {[KB[d]['id'] for d, _ in top]}  scores {[round(s, 4) for _, s in top]}")

    ctx.step("A weighted variant: trust vectors twice as much")
    weighted = {}
    for weight, ranking in ((1.0, kw_rank), (2.0, sem_rank)):
        for rank, doc in enumerate(ranking, 1):
            weighted[doc] = weighted.get(doc, 0.0) + weight / (60 + rank)
    ctx.note(f"top 3: {[KB[d]['id'] for d, _ in sorted(weighted.items(), key=lambda kv: -kv[1])[:3]]}")

    ctx.step("What to take away")
    ctx.note("RRF needs no score normalisation and no tuning to start with. Its fused scores are small")
    ctx.note("and only meaningful as an order, not as a confidence.")


if __name__ == "__main__":
    main()
