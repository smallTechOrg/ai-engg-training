"""04.3/1  Measuring retrieval: hit rate, recall and MRR on a labelled question set

Before judging answers, judge the retrieval that feeds them. `eval_set.json` holds 14 questions;
12 have a gold chunk that contains the answer, 2 are not in the KB. For each answerable question
we find the rank of its gold chunk, then report hit@1, hit@3 and MRR (mean reciprocal rank).
No chat model needed: this script only embeds.

Run it:   ./run 04.3/1          (Windows: run 04.3/1)
     or:  python modules/04-rag-by-hand/03-measuring-retrieval-and-answer-quality/01_retrieval_metrics.py
Needs the `rag` extra (local embedding model). No chat call.
"""

import json
from pathlib import Path

import numpy as np

from labkit import lesson

HERE = Path(__file__).parent
KB_DIR = HERE / "kb"


def load_chunks():
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        number = 0
        for paragraph in (p.strip() for p in path.read_text(encoding="utf-8").split("\n\n")):
            if not paragraph or paragraph.startswith("#") or paragraph.startswith("Updated:"):
                continue
            number += 1
            chunks.append({"source": f"{path.stem}#{number}", "text": paragraph})
    return chunks


def unit(m):
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


@lesson("04.3/1", "Retrieval metrics")
def main(ctx):
    ctx.step("1. Load the knowledge base and the labelled question set")
    chunks = load_chunks()
    items = json.loads((HERE / "eval_set.json").read_text(encoding="utf-8"))
    answerable = [q for q in items if q["gold"]]
    ctx.note(f"{len(chunks)} chunks; {len(items)} questions ({len(answerable)} answerable, {len(items) - len(answerable)} not in the KB).")
    ctx.note("A gold label says which chunk holds the answer. Writing these by hand is the real cost of evaluation.")

    ctx.step("2. Rank every chunk for every question (one batched embedding call each)")
    matrix = unit(np.array(ctx.embed([c["text"] for c in chunks])))
    qvecs = unit(np.array(ctx.embed([q["question"] for q in answerable])))
    scores = qvecs @ matrix.T
    ranks = []
    for q, row in zip(answerable, scores):
        order = [chunks[i]["source"] for i in np.argsort(-row)]
        rank = min(order.index(g) + 1 for g in q["gold"])  # best rank of any gold chunk, 1-based
        ranks.append(rank)
        flag = "" if rank == 1 else "   <-- not first"
        ctx.note(f"rank {rank:>2}  gold {q['gold'][0]:<13} top1 {order[0]:<13} {q['question'][:50]}{flag}")

    ctx.step("3. The metrics")
    n = len(ranks)
    for k in (1, 3, 5):
        ctx.note(f"hit@{k}: {sum(r <= k for r in ranks)}/{n} = {sum(r <= k for r in ranks) / n:.2f}   (gold chunk in the top {k})")
    mrr = sum(1 / r for r in ranks) / n
    ctx.note(f"MRR: {mrr:.2f}   (mean of 1/rank: 1.0 = always first, 0.5 = typically second)")
    ctx.note("With ONE gold chunk per question, recall@k equals hit@k. With several gold chunks, recall counts the fraction found.")

    ctx.step("4. The questions that are NOT in the KB")
    unanswerable = [q for q in items if not q["gold"]]
    uvecs = unit(np.array(ctx.embed([q["question"] for q in unanswerable])))
    best_out = (uvecs @ matrix.T).max(axis=1)
    best_in = scores.max(axis=1)
    for q, b in zip(unanswerable, best_out):
        ctx.note(f"best score {b:.2f}  {q['question']}")
    ctx.note(f"Answerable questions' best scores range {best_in.min():.2f}-{best_in.max():.2f}.")
    ctx.note("Hit rate cannot score these (there is no gold chunk). They test the refusal gate from 04.2 instead.")

    ctx.step("What to take away")
    ctx.note("hit@k tells you whether the answer was available to the model; MRR how high it ranked.")
    ctx.note("A tiny set (12) is a smoke test, not proof: one question moves hit@1 by 8 points.")


if __name__ == "__main__":
    main()
