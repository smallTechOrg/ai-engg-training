"""20.2/2  Add embeddings to retrieval and see what they change

Lexical search misses paraphrases: "my phone broke" shares no words with a page about authenticator
resets. Embeddings catch the meaning. This script builds the same knowledge base twice, once lexical and
once with `ctx.embed` (local fastembed unless you configured a hosted embedding model), and compares the
ranking on questions with and without word overlap.

Remember from module 04: embedding scores of unrelated text are never near zero, so the evidence gate
still uses the lexical share; the embedding only improves the ORDER. Where would a gate on cosine need
calibration against your own evaluation set?

Run it:   ./run 20.2/2          (Windows: run 20.2/2)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from larkspur_desk import KnowledgeBase  # noqa: E402

from labkit import lesson  # noqa: E402

HERE = Path(__file__).parent
QUESTIONS = [
    "I got a new phone, what happens to my login codes?",   # no shared words with the MFA page
    "Where do I get internet for a visitor?",               # paraphrase of guest Wi-Fi
    "How do I connect to the VPN?",                         # plenty of overlap
]


@lesson("20.2/2", "Add embeddings to retrieval and see what they change")
def main(ctx):
    ctx.step("Build the knowledge base twice: lexical, and with embeddings")
    lexical = KnowledgeBase(HERE / "kb")
    hybrid = KnowledgeBase(HERE / "kb", embed=ctx.embed)
    ctx.note(f"{len(hybrid.passages)} pages, embedded as {len(hybrid.vectors[0])}-dimension vectors")
    ctx.note("With a hosted provider the same call is client.embeddings.create(model=..., input=[...]); set EMBEDDING_MODEL in .env.")

    for question in QUESTIONS:
        ctx.step(f"Compare: {question}")
        for label, kb in [("lexical", lexical), ("embedding + lexical", hybrid)]:
            hits = kb.search(question, k=3)
            line = ", ".join(f"{h.passage.id} ({h.coverage:.0%}" + (f", cos {h.cosine:.2f}" if h.cosine is not None else "") + ")" for h in hits)
            ctx.note(f"{label:20s} {line}")
        gate = lexical.search(question, k=1)[0].coverage
        ctx.note(f"gate (lexical coverage {gate:.0%}) would {'pass' if gate >= 0.5 else 'hand over'}")

    ctx.step("What this shows")
    ctx.note("Embeddings reorder candidates; they do not make the gate safe. A paraphrase can rank first and still be")
    ctx.note("handed over by the lexical gate. Decide per project which error costs more: a wrong answer or a hand-over.")

    ctx.step("Your turn")
    ctx.note("Add three paraphrased questions of your own to evalset.json and see where the order changes.")


if __name__ == "__main__":
    main()
