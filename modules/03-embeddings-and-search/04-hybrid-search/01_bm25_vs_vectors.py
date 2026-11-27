"""03.4/1  Keyword search (BM25) and vector search disagree

BM25 scores documents by the words they share with the query, weighting rare words more.
Vectors score by meaning. Each is blind where the other sees. Four queries, both rankers,
side by side.

Run it:   ./run 03.4/1          (Windows: run 03.4/1)
Needs the `rag` extra (rank_bm25 + local embedding model). No chat model is used.
"""

import json
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from labkit import lesson

KB = json.loads(Path(__file__).with_name("kb.json").read_text(encoding="utf-8"))
QUERIES = [
    "HDMI",                                           # a rare exact word
    "Larkspur-Visitor",                               # an exact name
    "somebody took my handset",                       # no shared words with the right article
    "can't sign in after typing my password wrong",   # paraphrase with a few shared words
]


# Without a stop-word list, "my", "the" and "on" make BM25 match nearly every article a little.
STOP = {"a", "an", "the", "my", "i", "me", "to", "of", "on", "in", "at", "is", "it", "and", "or", "do", "does",
        "not", "no", "for", "with", "from", "if", "so", "be", "are", "was", "after", "when", "how", "what", "will", "can"}


def tokens(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


@lesson("03.4/1", "BM25 vs vector search")
def main(ctx):
    ctx.step("Build both indexes over the same 24 articles")
    bm25 = BM25Okapi([tokens(a["text"]) for a in KB])
    vectors = np.array(ctx.embed([a["text"] for a in KB]))
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    ctx.note("BM25 needs no model and no training: it only counts words. Vectors need the embedding model.")

    for query in QUERIES:
        ctx.step(f"Query: {query}")
        kw = bm25.get_scores(tokens(query))
        q = np.array(ctx.embed([query])[0])
        sem = vectors @ (q / np.linalg.norm(q))
        kw_top = np.argsort(-kw)[:3]
        sem_top = np.argsort(-sem)[:3]
        if kw[kw_top[0]] == 0:
            ctx.note("BM25: no article shares a word with the query (all scores 0).")
        else:
            for r, i in enumerate(kw_top, 1):
                ctx.note(f"BM25   #{r} ({kw[i]:5.2f}) {KB[i]['id']} {KB[i]['text'][:60]}")
        for r, i in enumerate(sem_top, 1):
            ctx.note(f"Vector #{r} ({sem[i]:5.2f}) {KB[i]['id']} {KB[i]['text'][:60]}")

    ctx.step("What to take away")
    ctx.note("BM25 scores are unbounded and vector scores are cosines in a narrow band: the two cannot")
    ctx.note("be added directly. 03.4/2 combines them by rank instead.")


if __name__ == "__main__":
    main()
