"""15.1/3  Scenario: fix two failures and re-measure

Two fixes, each aimed at one measured failure:

  * STALE CONTEXT -> metadata filter: never retrieve chunks from superseded documents.
  * SPLIT FACT    -> neighbour expansion: when a chunk is retrieved, also pull in the chunk
                     right after it in the same document (the same idea as larger chunks,
                     without re-indexing).

The test set is the one from script 2. Retrieval metrics cost nothing, so they are measured
for all five questions before and after. The two affected questions are then answered and
judged again, so you can see the effect on real answers.

Run it:   ./run 15.1/3          (Windows: run 15.1/3)
"""

import math
from pathlib import Path

import openai
from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
TOP_K = 2

SYSTEM_PROMPT = """You are the IT helpdesk assistant at Larkspur Labs.
Answer using ONLY the context below. If the context does not contain the answer, say you do not know.
Keep the answer to two sentences."""

TEST_SET = [
    {"question": "How much can I spend on a standing desk through the home office stipend?", "expected": ["stipend#1"]},
    {"question": "How long is a VPN session before I need an authenticator code again?", "expected": ["vpn-2025#1"]},
    {"question": "How often are laptops replaced?", "expected": ["laptop-faq#0", "laptop-guide#0"]},
    {"question": "I forgot my password and lost my security key. What do I do?", "expected": ["password#1"]},
    {"question": "Does Larkspur Labs offer pet insurance?", "expected": []},
]
AFFECTED = [0, 1]  # indexes into TEST_SET that the two fixes target


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: int
    faithful: bool
    unsupported_claim: str


class Verdicts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdicts: list[Verdict]


JUDGE_PROMPT = """You check answers from a helpdesk assistant against the context it was given.
For each numbered item decide: is EVERY claim in the answer supported by the context?
Judge support only, not whether the claim is true in the real world.
"I do not know" with no other claims counts as faithful.
Return one verdict per item."""


def load_chunks():
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        header, _, body = path.read_text(encoding="utf-8").partition("\n\n")
        meta = dict(line.split(": ", 1) for line in header.splitlines())
        for position, paragraph in enumerate(p.strip() for p in body.split("\n\n") if p.strip()):
            chunks.append({"id": f"{meta['id']}#{position}", "doc": meta["id"], "position": position,
                           "status": meta["status"], "text": paragraph})
    return chunks


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def retrieve(query_vector, chunks, vectors, drop_superseded, add_neighbours):
    """Top-k by cosine similarity, with the two optional fixes."""
    candidates = list(zip(vectors, chunks))
    if drop_superseded:
        # Fix 1: filter on metadata BEFORE ranking, so stale chunks cannot take a top-k slot.
        candidates = [(v, c) for v, c in candidates if not c["status"].startswith("superseded")]
    candidates.sort(key=lambda pair: cosine(query_vector, pair[0]), reverse=True)
    picked = [c for _, c in candidates[:TOP_K]]
    if add_neighbours:
        # Fix 2: also take the next chunk of the same document, so a fact split across two
        # paragraphs arrives whole.
        by_key = {(c["doc"], c["position"]): c for c in chunks}
        for chunk in list(picked):
            follower = by_key.get((chunk["doc"], chunk["position"] + 1))
            if follower is not None and follower not in picked:
                picked.append(follower)
    return picked


@lesson("15.1/3", "Fix stale and split facts, then re-measure")
def main(ctx):
    ctx.step("Index the knowledge base")
    chunks = load_chunks()
    vectors = ctx.embed([c["text"] for c in chunks])
    question_vectors = ctx.embed([item["question"] for item in TEST_SET])
    ctx.note(f"{len(chunks)} chunks indexed, {len(TEST_SET)} test questions.")

    ctx.step("Re-measure retrieval: before and after")
    configs = {"before (plain top-k)": (False, False), "after (filter + neighbours)": (True, True)}
    retrieved = {}
    for label, (drop, neighbours) in configs.items():
        retrieved[label] = [retrieve(qv, chunks, vectors, drop, neighbours) for qv in question_vectors]
        answerable = [(item, got) for item, got in zip(TEST_SET, retrieved[label]) if item["expected"]]
        hits = sum(1 for item, got in answerable if set(item["expected"]) & {c["id"] for c in got})
        stale = sum(1 for got in retrieved[label] if any(c["status"].startswith("superseded") for c in got))
        avg_chunks = sum(len(got) for got in retrieved[label]) / len(retrieved[label])
        ctx.show_data(label, {"hit_rate": f"{hits}/{len(answerable)}",
                              "questions with a stale chunk": f"{stale}/{len(TEST_SET)}",
                              "average chunks in the prompt": round(avg_chunks, 1)})
    ctx.note("The fixes are not free: neighbour expansion puts more text in every prompt.")

    ctx.step("Answer the two affected questions with both retrievers")
    rows = []
    for label in configs:
        for index in AFFECTED:
            got = retrieved[label][index]
            context = "\n\n".join(f"[{c['id']}] {c['text']}" for c in got)
            response = ctx.client.chat.completions.create(
                model=ctx.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + "\n\nContext:\n" + context},
                    {"role": "user", "content": TEST_SET[index]["question"]},
                ],
            )
            ctx.record_usage(response.usage, quiet=True)
            answer = response.choices[0].message.content or ""
            rows.append({"label": label, "question": TEST_SET[index]["question"], "context": context, "answer": answer})
            ctx.note(f"{label} | {[c['id'] for c in got]}")
            ctx.note(f"    {TEST_SET[index]['question']}")
            ctx.note(f"    -> {answer}")

    ctx.step("Judge faithfulness of all four answers (one batched call)")
    items = "\n\n".join(
        f"Item {n}\nContext:\n{r['context']}\nQuestion: {r['question']}\nAnswer: {r['answer']}"
        for n, r in enumerate(rows, start=1)
    )
    messages = [{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": items}]
    try:
        response = ctx.client.chat.completions.create(
            model=ctx.model, messages=messages,
            response_format={"type": "json_schema",
                             "json_schema": {"name": "verdicts", "schema": Verdicts.model_json_schema(), "strict": True}},
        )
    except (openai.BadRequestError, openai.UnprocessableEntityError):
        ctx.note("This endpoint refused json_schema; falling back to JSON mode.")
        messages[0]["content"] += '\nReply with JSON: {"verdicts": [{"number": 1, "faithful": true, "unsupported_claim": ""}]}'
        response = ctx.client.chat.completions.create(
            model=ctx.model, messages=messages, response_format={"type": "json_object"})
    ctx.record_usage(response.usage, quiet=True)
    try:
        verdicts = {v.number: v for v in Verdicts.model_validate_json(response.choices[0].message.content or "").verdicts}
    except (ValidationError, ValueError):
        ctx.note("The judge did not return valid verdicts, so faithfulness is not scored this run.")
        verdicts = {}
    for n, r in enumerate(rows, start=1):
        v = verdicts.get(n)
        ctx.note(f"{r['label']:<30} faithful={v.faithful if v else 'not judged'}  {r['question'][:45]}")

    ctx.step("What changed, and what did not")
    ctx.note("Hit rate and stale rate moved because the retriever changed. The answers moved because the")
    ctx.note("context changed. Nothing about the model or the prompt did. Still open: the duplicate laptop")
    ctx.note("documents waste a slot, and the pet-insurance question still pulls in unrelated chunks.")
    ctx.note("Deciding WHEN to retrieve, and retrying with a better query, is agentic RAG (lesson 15.2).")


if __name__ == "__main__":
    main()
