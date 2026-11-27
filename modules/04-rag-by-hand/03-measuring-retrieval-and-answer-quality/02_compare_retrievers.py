"""04.3/2  Use the metrics to choose: four retrievers, one scoreboard

A metric earns its keep when it settles an argument. Same 12 labelled questions, four ways to retrieve:
  keyword   - count shared words (no embeddings): the baseline to beat
  paragraph - embed each paragraph (what 04.1 does)
  titled    - embed "<file heading>: <paragraph>" so a chunk knows which document it came from
  wholefile - embed each entire file (scored at file level, so it is the easiest to hit)
No chat model needed.

Run it:   ./run 04.3/2          (Windows: run 04.3/2)
     or:  python modules/04-rag-by-hand/03-measuring-retrieval-and-answer-quality/02_compare_retrievers.py
Needs the `rag` extra (local embedding model). No chat call.
"""

import json
import re
from pathlib import Path

import numpy as np

from labkit import lesson

HERE = Path(__file__).parent
KB_DIR = HERE / "kb"
STOP = set("a an the of to is are do does i my me we how what can it in on or and for who be if you your at by with so".split())


def load():
    chunks, files = [], []
    for path in sorted(KB_DIR.glob("*.md")):
        paras = [p.strip() for p in path.read_text(encoding="utf-8").split("\n\n") if p.strip()]
        title = paras[0].lstrip("# ").strip()
        body = [p for p in paras if not p.startswith("#") and not p.startswith("Updated:")]
        for n, p in enumerate(body, start=1):
            chunks.append({"source": f"{path.stem}#{n}", "file": path.stem, "title": title, "text": p})
        files.append({"source": path.stem, "text": f"{title}\n\n" + "\n\n".join(body)})
    return chunks, files


def words(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP}


def unit(m):
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


def rank_of(order, gold):
    return min(order.index(g) + 1 for g in gold)


@lesson("04.3/2", "Comparing retrievers with metrics")
def main(ctx):
    ctx.step("1. Load chunks and the labelled questions")
    chunks, files = load()
    items = [q for q in json.loads((HERE / "eval_set.json").read_text(encoding="utf-8")) if q["gold"]]
    questions = [q["question"] for q in items]
    ctx.note(f"{len(chunks)} paragraph chunks, {len(files)} whole files, {len(items)} labelled questions.")

    ctx.step("2. Build the four rankings")
    qvecs = unit(np.array(ctx.embed(questions)))
    orders = {}

    # keyword baseline: number of shared (non-stop) words
    orders["keyword"] = []
    for q in questions:
        qw = words(q)
        sc = [len(qw & words(c["text"])) for c in chunks]
        # stable sort: ties keep file order, which is arbitrary, and that is the point of a weak baseline
        orders["keyword"].append([chunks[i]["source"] for i in sorted(range(len(chunks)), key=lambda i: -sc[i])])

    pm = unit(np.array(ctx.embed([c["text"] for c in chunks])))
    orders["paragraph"] = [[chunks[i]["source"] for i in np.argsort(-row)] for row in qvecs @ pm.T]

    tm = unit(np.array(ctx.embed([f"{c['title']}: {c['text']}" for c in chunks])))
    orders["titled"] = [[chunks[i]["source"] for i in np.argsort(-row)] for row in qvecs @ tm.T]

    fm = unit(np.array(ctx.embed([f["text"] for f in files])))
    orders["wholefile"] = [[files[i]["source"] for i in np.argsort(-row)] for row in qvecs @ fm.T]
    ctx.note("wholefile ranks 6 files, so its gold is the file name (laptops#2 -> laptops). It is not comparable on hit@1.")

    ctx.step("3. The scoreboard")
    ctx.note(f"{'retriever':<10} {'hit@1':>6} {'hit@3':>6} {'MRR':>6}")
    table = {}
    for name, per_q in orders.items():
        ranks = []
        for q, order in zip(items, per_q):
            gold = [g.split("#")[0] for g in q["gold"]] if name == "wholefile" else q["gold"]
            ranks.append(rank_of(order, gold))
        table[name] = ranks
        n = len(ranks)
        ctx.note(f"{name:<10} {sum(r == 1 for r in ranks) / n:>6.2f} {sum(r <= 3 for r in ranks) / n:>6.2f} {sum(1 / r for r in ranks) / n:>6.2f}")

    ctx.step("4. Where do they disagree?")
    for i, q in enumerate(items):
        r = {name: table[name][i] for name in table}
        if len(set(r[n] for n in ("keyword", "paragraph", "titled"))) > 1:
            ctx.note(f"{q['question'][:48]:<48} " + "  ".join(f"{n}={r[n]}" for n in ("keyword", "paragraph", "titled")))

    ctx.step("What to take away")
    ctx.note("One scoreboard turns 'embeddings feel better' into a number you can defend, and re-run after each change.")
    ctx.note("Do not over-read 12 questions: differences of one question are noise. Grow the set before big decisions.")
    ctx.note("The whole-file row looks great because the task got easier; always compare like with like.")


if __name__ == "__main__":
    main()
