"""15.1/2  Diagnose RAG with numbers, not impressions

Reading retrieved chunks by eye does not scale. Here we turn "it feels wrong" into three
measurable checks over a small test set:

  1. Retrieval hit rate: did the chunk that holds the answer come back in the top-k?
  2. Stale rate:         did a superseded document come back?
  3. Faithfulness:       is every claim in the answer supported by the retrieved context?
                         (judged by a second model call that returns structured output)

This is exactly what evaluation libraries such as RAGAS automate (they call the checks
context recall, faithfulness and so on). Writing them by hand once shows what they do.

Run it:   ./run 15.1/2          (Windows: run 15.1/2)
"""

import json
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

# expected = chunk ids ("document#paragraph") that hold the answer; any one of them is a hit.
# An empty list means the KB cannot answer: the right behaviour is to say so.
TEST_SET = [
    {"question": "How much can I spend on a standing desk through the home office stipend?", "expected": ["stipend#1"]},
    {"question": "How long is a VPN session before I need an authenticator code again?", "expected": ["vpn-2025#1"]},
    {"question": "How often are laptops replaced?", "expected": ["laptop-faq#0", "laptop-guide#0"]},
    {"question": "I forgot my password and lost my security key. What do I do?", "expected": ["password#1"]},
    {"question": "Does Larkspur Labs offer pet insurance?", "expected": []},
]


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: int            # which test question this verdict is for
    faithful: bool         # every claim in the answer is supported by the context
    unsupported_claim: str  # the first unsupported claim, or "" if none


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
            chunks.append({"id": f"{meta['id']}#{position}", "doc": meta["id"], "status": meta["status"],
                           "effective": meta["effective"], "text": paragraph})
    return chunks


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


@lesson("15.1/2", "Measure retrieval and faithfulness")
def main(ctx):
    ctx.step("Index the knowledge base")
    chunks = load_chunks()
    vectors = ctx.embed([c["text"] for c in chunks])
    ctx.note(f"{len(chunks)} chunks indexed. Test set: {len(TEST_SET)} questions, top-k = {TOP_K}.")

    ctx.step("Retrieve and answer every test question")
    results = []
    for number, item in enumerate(TEST_SET, start=1):
        query_vector = ctx.embed([item["question"]])[0]
        ranked = sorted(zip(vectors, chunks), key=lambda pair: cosine(query_vector, pair[0]), reverse=True)
        top = [(cosine(query_vector, v), c) for v, c in ranked[:TOP_K]]
        context = "\n\n".join(f"[{c['id']}] {c['text']}" for _, c in top)
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + "\n\nContext:\n" + context},
                {"role": "user", "content": item["question"]},
            ],
        )
        ctx.record_usage(response.usage, quiet=True)
        answer = response.choices[0].message.content or ""
        retrieved = [c["id"] for _, c in top]
        results.append({"number": number, "question": item["question"], "expected": item["expected"],
                        "retrieved": retrieved, "context": context, "answer": answer,
                        "stale": any(c["status"].startswith("superseded") for _, c in top)})
        ctx.note(f"Q{number}: retrieved {retrieved}")

    ctx.step("Check 1 and 2: retrieval hit rate and stale rate (no model needed)")
    answerable = [r for r in results if r["expected"]]
    for r in results:
        hit = "n/a (KB cannot answer)" if not r["expected"] else ("HIT" if set(r["expected"]) & set(r["retrieved"]) else "MISS")
        ctx.note(f"Q{r['number']}: {hit:<24} stale chunk retrieved: {r['stale']}")
    hits = sum(1 for r in answerable if set(r["expected"]) & set(r["retrieved"]))
    ctx.show_data("Retrieval metrics", {
        "hit_rate": f"{hits}/{len(answerable)}",
        "stale_rate": f"{sum(r['stale'] for r in results)}/{len(results)} questions got a superseded chunk",
    })

    ctx.step("Check 3: faithfulness, judged by a model with structured output")
    ctx.note("One batched call judges all answers. The reply is forced into the Verdicts schema.")
    items = "\n\n".join(
        f"Item {r['number']}\nContext:\n{r['context']}\nQuestion: {r['question']}\nAnswer: {r['answer']}" for r in results
    )
    messages = [{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": items}]
    try:
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=messages,
            response_format={"type": "json_schema",
                             "json_schema": {"name": "verdicts", "schema": Verdicts.model_json_schema(), "strict": True}},
        )
    except (openai.BadRequestError, openai.UnprocessableEntityError):
        ctx.note("This endpoint refused json_schema; falling back to JSON mode with the shape in the prompt.")
        shape = '\nReply with JSON: {"verdicts": [{"number": 1, "faithful": true, "unsupported_claim": ""}]}'
        messages[0]["content"] += shape
        response = ctx.client.chat.completions.create(
            model=ctx.model, messages=messages, response_format={"type": "json_object"})
    ctx.show_response(response)
    try:
        verdicts = Verdicts.model_validate_json(response.choices[0].message.content or "")
    except (ValidationError, ValueError):
        ctx.note("The judge did not return valid verdicts, so faithfulness is not scored this run.")
        verdicts = Verdicts(verdicts=[])
    for v in verdicts.verdicts:
        if v.unsupported_claim.strip().lower() in ("null", "none", "n/a"):
            v.unsupported_claim = ""  # models sometimes write the word instead of an empty string
    by_number = {v.number: v for v in verdicts.verdicts}
    for r in results:
        v = by_number.get(r["number"])
        if v is None:
            ctx.note(f"Q{r['number']}: no verdict")
        else:
            ctx.note(f"Q{r['number']}: faithful={v.faithful}" + (f"  unsupported: {v.unsupported_claim}" if v.unsupported_claim else ""))
    judged = [by_number[r["number"]] for r in results if r["number"] in by_number]
    ctx.show_data("Faithfulness", {"faithful": f"{sum(v.faithful for v in judged)}/{len(judged)} judged answers"})

    ctx.step("Read the numbers together")
    ctx.note("Faithfulness asks 'did the answer stick to the context?', not 'is it right?'. A model can be")
    ctx.note("perfectly faithful to a stale or incomplete context. That is why hit rate and stale rate")
    ctx.note("come first: they tell you whether the context was any good. RAGAS reports the same families")
    ctx.note("of metrics (context recall/precision, faithfulness, answer relevancy) with LLM judges.")
    ctx.note("An LLM judge is itself a model: spot-check its verdicts before trusting the score.")


if __name__ == "__main__":
    main()
