"""15.1/1  Plain RAG and three ways it fails

Plain RAG: chunk the documents, embed the chunks, embed the question, take the top-k chunks
by cosine similarity, paste them into the prompt. It works until it does not. This script
runs it on a small invented knowledge base (the `kb/` folder next to this file) with
questions chosen to trigger a different failure each time.

Run it:   ./run 15.1/1          (Windows: run 15.1/1)
"""

import math
from pathlib import Path

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
TOP_K = 2

SYSTEM_PROMPT = """You are the IT helpdesk assistant at Larkspur Labs.
Answer using ONLY the context below. If the context does not contain the answer, say you do not know.
Keep the answer to two sentences."""

# (failure we expect, question)
QUESTIONS = [
    ("MISSED RETRIEVAL (the answer is in a chunk that never arrives)",
     "How much can I spend on a standing desk through the home office stipend?"),
    ("STALE CONTEXT (an outdated policy competes with its replacement)",
     "How long is a VPN session before I need an authenticator code again?"),
    ("IRRELEVANT CONTEXT (nothing in the KB answers it, but top-k returns something anyway)",
     "Does Larkspur Labs offer pet insurance?"),
]


def load_chunks():
    """One chunk per paragraph. Each chunk remembers which document it came from."""
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        header, _, body = path.read_text(encoding="utf-8").partition("\n\n")
        meta = dict(line.split(": ", 1) for line in header.splitlines())
        for position, paragraph in enumerate(p.strip() for p in body.split("\n\n") if p.strip()):
            chunks.append({"doc": meta["id"], "effective": meta["effective"],
                           "position": position, "text": paragraph})
    return chunks


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


@lesson("15.1/1", "Plain RAG and its failures")
def main(ctx):
    ctx.step("Chunk and embed the knowledge base")
    chunks = load_chunks()
    ctx.note(f"{len(chunks)} chunks from {len(list(KB_DIR.glob('*.md')))} documents (one chunk per paragraph).")
    # ctx.embed runs a local model unless EMBEDDING_MODEL names a hosted one. With a provider
    # that offers embeddings this is client.embeddings.create(model=..., input=[...]).
    vectors = ctx.embed([c["text"] for c in chunks])
    ctx.note(f"Each chunk is now a vector of {len(vectors[0])} numbers.")

    for failure, question in QUESTIONS:
        ctx.step(failure.split(" (")[0].capitalize())
        ctx.note(failure)
        ctx.note("Question: " + question)
        query_vector = ctx.embed([question])[0]
        ranked = sorted(zip(vectors, chunks), key=lambda pair: cosine(query_vector, pair[0]), reverse=True)
        top = [(cosine(query_vector, v), c) for v, c in ranked[:TOP_K]]
        for score, chunk in top:
            ctx.note(f"  score {score:.2f}  [{chunk['doc']} #{chunk['position']}, {chunk['effective']}]  {chunk['text'][:90]}")

        context = "\n\n".join(f"[{c['doc']}] {c['text']}" for _, c in top)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + "\n\nContext:\n" + context},
            {"role": "user", "content": question},
        ]
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        ctx.show_response(response)

    ctx.step("What to take away")
    ctx.note("Look at the retrieved chunks above, not just the answers. The retriever did the wrong")
    ctx.note("thing three times: it returned the facility-ordering chunk but not the 400 USD chunk,")
    ctx.note("it ranked the superseded 2023 VPN policy first, and it returned unrelated chunks for a")
    ctx.note("question the KB cannot answer. The model may paper over some of this (it often")
    ctx.note("prefers the newer policy, or says it does not know), but you cannot count on that.")
    ctx.note("Nothing crashed. RAG failures are silent, so script 2 measures them.")


if __name__ == "__main__":
    main()
