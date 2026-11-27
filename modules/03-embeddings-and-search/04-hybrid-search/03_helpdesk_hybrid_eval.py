"""03.4/3  Does hybrid search help the helpdesk? Measure it.

Eleven helpdesk questions, each with the article that should be found. We run BM25, vectors
and the RRF mix, and report where the right article ranks. An optional team filter shows
filtering before fusion. Small test set: read the numbers as a demonstration of the method,
not as a verdict.

Run it:   ./run 03.4/3          (Windows: run 03.4/3)
Needs the `rag` extra (rank_bm25 + local embedding model). No chat model is used.
"""

import json
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from labkit import lesson

KB = json.loads(Path(__file__).with_name("kb.json").read_text(encoding="utf-8"))
# (question, id of the article that answers it, optional team filter)
CASES = [
    ("HDMI cable does not work in the boardroom", "KB-013", None),
    ("what is the Larkspur-Visitor password", "KB-005", None),
    ("somebody took my handset on the train", "KB-011", None),
    ("my login is blocked after too many tries", "KB-002", None),
    ("new authenticator after replacing my mobile", "KB-003", None),
    ("internal sites will not load while VPN says connected", "KB-007", None),
    ("how long do I have to restart after updates", "KB-018", None),
    ("was I phished, I clicked a bad link", "KB-020", None),
    ("who approves access to a shared mailbox", "KB-022", None),
    ("need a security key for payments", "KB-024", None),
    ("printer offline", "KB-012", "hardware"),
]


# Without a stop-word list, "my", "the" and "on" make BM25 match nearly every article a little.
STOP = {"a", "an", "the", "my", "i", "me", "to", "of", "on", "in", "at", "is", "it", "and", "or", "do", "does",
        "not", "no", "for", "with", "from", "if", "so", "be", "are", "was", "after", "when", "how", "what", "will", "can"}


def tokens(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def rrf(rankings, k=60):
    fused = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, 1):
            fused[doc] = fused.get(doc, 0.0) + 1.0 / (k + rank)
    return [d for d, _ in sorted(fused.items(), key=lambda kv: -kv[1])]


@lesson("03.4/3", "Hybrid search for the helpdesk, measured")
def main(ctx):
    ctx.step("Index")
    bm25 = BM25Okapi([tokens(a["text"]) for a in KB])
    vectors = np.array(ctx.embed([a["text"] for a in KB]))
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    q_vectors = np.array(ctx.embed([c[0] for c in CASES]))
    q_vectors /= np.linalg.norm(q_vectors, axis=1, keepdims=True)
    ids = [a["id"] for a in KB]

    ctx.step("Rank of the correct article (1 = best)")
    ctx.note(f"{'question':<52} {'BM25':>5} {'vec':>5} {'RRF':>5} {'RRF0':>5}")
    ranks = {"bm25": [], "vec": [], "rrf": [], "rrf0": []}
    for (question, answer, team), qv in zip(CASES, q_vectors):
        allowed = [i for i, a in enumerate(KB) if team is None or a["team"] == team]  # filter BEFORE ranking
        kw_scores = bm25.get_scores(tokens(question))
        kw = [i for i in np.argsort(-kw_scores) if i in allowed]
        kw_nonzero = [i for i in kw if kw_scores[i] > 0]  # BM25 only ranks documents it actually matched
        sem = [i for i in np.argsort(-(vectors @ qv)) if i in allowed]
        fused = rrf([kw, sem])
        fused0 = rrf([kw_nonzero, sem])  # RRF0: zero-score BM25 documents are left out of the fusion
        row = []
        for name, ranking in (("bm25", kw), ("vec", sem), ("rrf", fused), ("rrf0", fused0)):
            rank = [ids[i] for i in ranking].index(answer) + 1
            ranks[name].append(rank)
            row.append(rank)
        ctx.note(f"{question[:51]:<52} {row[0]:>5} {row[1]:>5} {row[2]:>5} {row[3]:>5}" + ("   (team filter)" if team else ""))

    ctx.step("Summary")
    ctx.note(f"{'method':<8} {'top-1':>6} {'top-3':>6} {'mean rank':>10}")
    for name in ("bm25", "vec", "rrf", "rrf0"):
        r = ranks[name]
        ctx.note(f"{name:<8} {sum(x == 1 for x in r):>3}/{len(r)} {sum(x <= 3 for x in r):>3}/{len(r)} {np.mean(r):>10.2f}")

    ctx.step("What to take away")
    ctx.note("Plain RRF lost ranks on the 'handset' and 'login' questions: BM25 matched no word of the")
    ctx.note("right article, yet its arbitrary order of zero-score ties still voted. RRF0 drops those. On this small, clean knowledge base vectors")
    ctx.note("alone are as good as hybrid; hybrid pays off with exact codes, names and jargon. Check on")
    ctx.note("your own questions: with 11 cases one question moves the totals a lot.")


if __name__ == "__main__":
    main()
