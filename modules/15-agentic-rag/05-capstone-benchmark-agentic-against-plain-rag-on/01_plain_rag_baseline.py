"""15.5/1  Capstone, part 1: the test set and the plain RAG baseline

The brief and acceptance criteria are in the README. This script builds the baseline everything else is
compared with: plain top-2 RAG over ALL documents (including the superseded VPN policy), scored by a
deterministic rule on `testset.json`:

  - answerable question: the answer must contain one of `any_of` and none of `none_of` (case-insensitive);
  - unanswerable question: the answer must DECLINE (it says it does not know) instead of inventing something.

No model judge is used, so the score is repeatable and free.

Run it:   ./run 15.5/1          (Windows: run 15.5/1)
"""

import json
import math
import re
from pathlib import Path

from labkit import lesson

HERE = Path(__file__).parent
TOP_K = 2
DECLINE = re.compile(r"do(?:es)? not know|don't know|not (?:in|contain|provid|mention|specif|cover)|no information|cannot (?:find|answer)|unable to (?:find|answer)", re.I)

SYSTEM_PROMPT = """You are the IT helpdesk assistant at Larkspur Labs.
Answer using ONLY the context below. If the context does not contain the answer, say you do not know.
Keep the answer to two sentences."""


def load_chunks():
    chunks = []
    for path in sorted((HERE / "kb").glob("*.md")):
        header, _, body = path.read_text(encoding="utf-8").partition("\n\n")
        meta = dict(line.split(": ", 1) for line in header.splitlines())
        for position, paragraph in enumerate(p.strip() for p in body.split("\n\n") if p.strip()):
            chunks.append({"id": f"{meta['id']}#{position}", "status": meta["status"], "text": paragraph})
    return chunks


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def passes(item, answer):
    """The deterministic scoring rule."""
    text = answer.lower()
    if not item["answerable"]:
        return bool(DECLINE.search(answer))
    return any(k.lower() in text for k in item["any_of"]) and not any(k.lower() in text for k in item["none_of"])


@lesson("15.5/1", "Capstone: the test set and the plain RAG baseline")
def main(ctx):
    ctx.step("The test set")
    test_set = json.loads((HERE / "testset.json").read_text(encoding="utf-8"))
    for n, item in enumerate(test_set, start=1):
        ctx.note(f"{n}. {'answerable  ' if item['answerable'] else 'UNANSWERABLE'} {item['question']}")

    ctx.step("Plain RAG: embed, top-2, answer (one model call per question)")
    chunks = load_chunks()
    vectors = ctx.embed([c["text"] for c in chunks])
    passed = 0
    for n, item in enumerate(test_set, start=1):
        qv = ctx.embed([item["question"]])[0]
        top = [c for _, c in sorted(zip(vectors, chunks), key=lambda pair: cosine(qv, pair[0]), reverse=True)[:TOP_K]]
        context = "\n\n".join(f"[{c['id']}] {c['text']}" for c in top)
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT + "\n\nContext:\n" + context},
                      {"role": "user", "content": item["question"]}])
        ctx.record_usage(response.usage, quiet=True)
        answer = response.choices[0].message.content or ""
        ok = passes(item, answer)
        passed += ok
        ctx.note(f"Q{n} {'PASS' if ok else 'FAIL'}  retrieved {[c['id'] for c in top]}")
        ctx.note(f"      {answer[:150]}")

    ctx.step("Baseline score")
    ctx.note(f"Plain RAG: {passed}/{len(test_set)} passed, {len(test_set)} model calls.")
    ctx.note("This is the number to beat. Remember that a model that paraphrases differently can flip a")
    ctx.note("keyword check: read the FAIL lines before trusting the score.")


if __name__ == "__main__":
    main()
