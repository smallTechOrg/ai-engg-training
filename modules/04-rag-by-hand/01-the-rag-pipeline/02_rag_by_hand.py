"""04.1/2  The RAG pipeline by hand: retrieve, augment, generate

Every stage written out: load the knowledge-base files, chunk by paragraph, embed, retrieve
the top-k chunks by cosine similarity, build the augmented prompt, and ask for an answer
that cites its sources. No framework, no vector database.

Run it:   ./run 04.1/2          (Windows: run 04.1/2)
     or:  python modules/04-rag-by-hand/01-the-rag-pipeline/02_rag_by_hand.py
Needs a chat model and the `rag` extra (local embedding model).
"""

from pathlib import Path

import numpy as np

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
QUESTION = "How often does Larkspur Labs replace employee laptops, and who do I contact if mine breaks early?"
TOP_K = 3


@lesson("04.1/2", "The RAG pipeline by hand")
def main(ctx):
    ctx.step("1. Load and chunk the knowledge base")
    ctx.note("Chunking here is the simplest useful rule: one paragraph = one chunk (better rules: lesson 03.2).")
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for number, paragraph in enumerate(p.strip() for p in text.split("\n\n")):
            if paragraph and not paragraph.startswith("#"):
                chunks.append({"source": f"{path.name}#{number}", "text": paragraph})
    ctx.note(f"{len(list(KB_DIR.glob('*.md')))} files -> {len(chunks)} chunks")

    ctx.step("2. Embed every chunk (done once, ahead of time)")
    matrix = np.array(ctx.embed([c["text"] for c in chunks]))
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    ctx.note(f"Index: {matrix.shape[0]} vectors x {matrix.shape[1]} numbers.")

    ctx.step("3. RETRIEVE: embed the question, take the top-k chunks")
    query = np.array(ctx.embed([QUESTION])[0])
    query = query / np.linalg.norm(query)
    scores = matrix @ query
    top = [int(i) for i in np.argsort(-scores)[:TOP_K]]
    ctx.note(f"Question: {QUESTION}")
    for rank, i in enumerate(top, start=1):
        ctx.note(f"#{rank} score {scores[i]:.2f}  [{chunks[i]['source']}]  {chunks[i]['text'][:70]}...")

    ctx.step("4. AUGMENT: build the prompt")
    context = "\n\n".join(f"[{chunks[i]['source']}]\n{chunks[i]['text']}" for i in top)
    system = (
        "You are the IT helpdesk assistant at Larkspur Labs. Answer using ONLY the context below. "
        "Cite the source label in square brackets after each fact, for example [laptops.md#1]."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Context:\n\n{context}\n\nQuestion: {QUESTION}"},
    ]
    ctx.note("This is exactly what the model will see. The 'augmentation' is just string building:")
    ctx.show_messages(messages)

    ctx.step("5. GENERATE: ask the model")
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    ctx.show_response(response)
    ctx.note("Check the citations against the retrieved chunks above. The model can still cite wrongly;")
    ctx.note("lessons 04.2 and 04.3 deal with that.")


if __name__ == "__main__":
    main()
