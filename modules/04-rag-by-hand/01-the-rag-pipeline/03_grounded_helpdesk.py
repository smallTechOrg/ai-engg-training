"""04.1/3  Scenario: grounded helpdesk answers, including one the KB cannot answer

Three employee questions answered from the Larkspur Labs knowledge base. The fourth topic
is not in the KB; the prompt says "say you don't know", and we check that it does.

Run it:   ./run 04.1/3          (Windows: run 04.1/3)
     or:  python modules/04-rag-by-hand/01-the-rag-pipeline/03_grounded_helpdesk.py
Needs a chat model and the `rag` extra (local embedding model).
"""

from pathlib import Path

import numpy as np

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
TOP_K = 2
QUESTIONS = [
    "I forgot my password, how do I get back in?",
    "Can I get Slack-style chat licences for contractors? Who approves software costing 500 pounds a year?",
    "The printer on my floor is offline, what should I try?",
    "What is the company's parental leave policy?",  # not in the KB on purpose
]
SYSTEM = (
    "You are the IT helpdesk assistant at Larkspur Labs. Answer ONLY from the context provided. "
    "Cite sources in square brackets, for example [wifi.md#1]. "
    "If the context does not contain the answer, say exactly: \"I don't know based on the IT knowledge base.\" "
    "and suggest contacting the helpdesk. Never guess."
)


@lesson("04.1/3", "Grounded helpdesk answers")
def main(ctx):
    ctx.step("Build the index")
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        for number, paragraph in enumerate(p.strip() for p in path.read_text(encoding="utf-8").split("\n\n")):
            if paragraph and not paragraph.startswith("#"):
                chunks.append({"source": f"{path.name}#{number}", "text": paragraph})
    matrix = np.array(ctx.embed([c["text"] for c in chunks]))
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    ctx.note(f"{len(chunks)} chunks indexed.")

    # One embedding call for all the questions (batching), then one chat call each.
    question_vectors = np.array(ctx.embed(QUESTIONS))
    question_vectors = question_vectors / np.linalg.norm(question_vectors, axis=1, keepdims=True)

    for question, qvec in zip(QUESTIONS, question_vectors):
        ctx.step(f"Question: {question}")
        scores = matrix @ qvec
        top = [int(i) for i in np.argsort(-scores)[:TOP_K]]
        for i in top:
            ctx.note(f"retrieved {chunks[i]['source']} (score {scores[i]:.2f})")
        context = "\n\n".join(f"[{chunks[i]['source']}]\n{chunks[i]['text']}" for i in top)
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context:\n\n{context}\n\nQuestion: {question}"},
        ]
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        reply = ctx.show_response(response)
        if "don't know" in (reply or "").lower() or "do not know" in (reply or "").lower():
            ctx.note("-> The assistant declined: the retrieved chunks did not hold the answer.")

    ctx.step("What to take away")
    ctx.note("Retrieval never returns 'nothing': it returns the nearest chunks, relevant or not.")
    ctx.note("The safety valve is the prompt rule plus a model that follows it. Test it, as we just did.")


if __name__ == "__main__":
    main()
