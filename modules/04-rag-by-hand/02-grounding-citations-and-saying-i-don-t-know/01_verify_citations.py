"""04.2/1  Citations you can check: structured answers with verbatim quotes

04.1 asked the model to cite in square brackets. That is a request, not a guarantee. Here the
model must return JSON: an answer, and for every claim a source label plus a verbatim quote.
Ordinary code then checks each citation against the chunks that were actually retrieved:
is the label one we supplied, and is the quote really in that chunk?

Run it:   ./run 04.2/1          (Windows: run 04.2/1)
     or:  python modules/04-rag-by-hand/02-grounding-citations-and-saying-i-don-t-know/01_verify_citations.py
Needs a chat model and the `rag` extra (local embedding model).
"""

from pathlib import Path

import numpy as np
from pydantic import BaseModel, ValidationError

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
QUESTION = "How long do I have to return my old laptop, and what happens to it?"
TOP_K = 3


class Citation(BaseModel):
    source: str
    quote: str


class GroundedAnswer(BaseModel):
    answer: str
    citations: list[Citation]


def load_chunks():
    """One chunk per content paragraph; 'Updated:' lines become metadata, headings are skipped."""
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        updated, number = "unknown", 0
        for paragraph in (p.strip() for p in path.read_text(encoding="utf-8").split("\n\n")):
            if not paragraph or paragraph.startswith("#"):
                continue
            if paragraph.startswith("Updated:"):
                updated = paragraph.split(":", 1)[1].strip()
                continue
            number += 1
            chunks.append({"source": f"{path.stem}#{number}", "text": paragraph, "updated": updated})
    return chunks


def check_citations(answer: GroundedAnswer, retrieved: dict) -> list[str]:
    """Return a list of problems; an empty list means every citation checks out."""
    problems = []
    if not answer.citations:
        problems.append("no citations at all")
    for c in answer.citations:
        if c.source not in retrieved:
            problems.append(f"{c.source}: not one of the chunks we supplied (invented label)")
        elif " ".join(c.quote.split()).lower() not in " ".join(retrieved[c.source].split()).lower():
            problems.append(f"{c.source}: quote is not in that chunk: {c.quote[:50]!r}")
    return problems


@lesson("04.2/1", "Citations you can check")
def main(ctx):
    ctx.step("1. Index and retrieve (as in 04.1)")
    chunks = load_chunks()
    matrix = np.array(ctx.embed([c["text"] for c in chunks]))
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    query = np.array(ctx.embed([QUESTION])[0])
    query = query / np.linalg.norm(query)
    scores = matrix @ query
    top = [int(i) for i in np.argsort(-scores)[:TOP_K]]
    retrieved = {chunks[i]["source"]: chunks[i]["text"] for i in top}
    for i in top:
        ctx.note(f"score {scores[i]:.2f}  [{chunks[i]['source']}]  {chunks[i]['text'][:60]}...")

    ctx.step("2. Ask for JSON with a verbatim quote per claim")
    context = "\n\n".join(f"[{s}]\n{t}" for s, t in retrieved.items())
    system = (
        "You are the IT helpdesk assistant at Larkspur Labs. Answer ONLY from the context. "
        'Reply as JSON: {"answer": "<short answer>", "citations": [{"source": "<label>", "quote": '
        '"<exact words copied from that chunk>"}]}. Every claim needs a citation. '
        'If the context does not answer, use "I don\'t know based on the IT knowledge base." and an empty list.'
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Context:\n\n{context}\n\nQuestion: {QUESTION}"},
    ]
    response = ctx.client.chat.completions.create(
        model=ctx.model, messages=messages, response_format={"type": "json_object"}
    )
    raw = ctx.show_response(response)

    ctx.step("3. Validate the shape, then verify every citation in code")
    try:
        answer = GroundedAnswer.model_validate_json(raw or "")
    except ValidationError as err:
        ctx.note(f"The reply was not the JSON shape we asked for ({err.error_count()} problem(s)). Treat as ungrounded.")
        answer = None
    if answer:
        problems = check_citations(answer, retrieved)
        ctx.show_data("verification", {"answer": answer.answer, "citations": len(answer.citations), "problems": problems})
        ctx.note("All citations verified." if not problems else "Some citations failed: do not show this answer as grounded.")

    ctx.step("4. Prove the checker catches bad citations (no model call)")
    fake = GroundedAnswer(
        answer="Return it within 30 days.",
        citations=[
            Citation(source="laptops#3", quote="Return the old laptop to IT within 14 days"),
            Citation(source="laptops#9", quote="within 30 days"),
            Citation(source="laptops#3", quote="within 30 days of purchase"),
        ],
    )
    ctx.note("Hand-made answer: one good citation, one invented label, one quote that is not in the chunk.")
    real_label = next((s for s in retrieved if s.startswith("laptops#")), None)
    if real_label:
        fake.citations[0].source = fake.citations[2].source = real_label
    ctx.show_data("checker on the hand-made answer", {"problems": check_citations(fake, retrieved)})
    ctx.note("A prompt can ask for citations; only code can prove them. Keep both.")


if __name__ == "__main__":
    main()
