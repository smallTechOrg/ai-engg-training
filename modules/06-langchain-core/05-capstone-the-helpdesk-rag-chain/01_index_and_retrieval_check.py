"""06.5/1  Capstone step 1: build the index and test retrieval before adding a model

Part of the capstone brief (see README): the helpdesk RAG chain. Retrieval quality caps answer quality, so
we test it first, with no chat model: for each question we know which knowledge-base file holds the answer,
and we count how often that file is in the top k chunks (a "hit rate", also called recall at k).

Run it:   ./run 06.5/1          (Windows: run 06.5/1)
"""

import warnings
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"


class LabEmbeddings(Embeddings):
    """LangChain Embeddings over the course helper (local model unless EMBEDDING_MODEL is set)."""

    def __init__(self, ctx):
        self.ctx = ctx

    def embed_documents(self, texts):
        return self.ctx.embed(texts)

    def embed_query(self, text):
        return self.ctx.embed([text])[0]


def build_store(ctx):
    """Load the KB, split, embed, store. Returns (store, chunks)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from langchain_community.document_loaders import TextLoader
    docs = []
    for path in sorted(KB_DIR.glob("*.md")):
        for d in TextLoader(str(path), encoding="utf-8").load():
            d.metadata["source"] = path.name
            docs.append(d)
    chunks = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=60).split_documents(docs)
    return InMemoryVectorStore.from_documents(chunks, LabEmbeddings(ctx)), chunks


# (question, file that holds the answer). None = the KB has no answer.
CASES = [
    ("I forgot my password, how do I get back in?", "passwords.md"),
    ("My account is locked after too many tries", "passwords.md"),
    ("The printer on my floor is offline", "printers.md"),
    ("The VPN will not connect from home", "vpn.md"),
    ("The Wi-Fi keeps dropping in meeting rooms", "wifi.md"),
    ("How often are laptops replaced?", "laptops.md"),
    ("Who approves software that costs a lot?", "software.md"),
    ("When do I collect my laptop on my first day?", "onboarding.md"),
    ("What is the parental leave policy?", None),
]


@lesson("06.5/1", "Capstone 1: index and retrieval check")
def main(ctx):
    ctx.step("Build the index")
    store, chunks = build_store(ctx)
    ctx.note(f"{len(chunks)} chunks from {len({c.metadata['source'] for c in chunks})} files.")

    ctx.step("Hit rate at k=1 and k=3")
    rows, hits1, hits3, scored = [], 0, 0, 0
    for question, expected in CASES:
        results = store.similarity_search_with_score(question, k=3)
        sources = [doc.metadata["source"] for doc, _ in results]
        top_score = round(results[0][1], 2)
        if expected is None:
            rows.append({"question": question, "expected": "(none)", "top3": sources, "top_score": top_score})
            continue
        scored += 1
        hit1, hit3 = sources[0] == expected, expected in sources
        hits1 += hit1
        hits3 += hit3
        rows.append({"question": question, "expected": expected, "top3": sources, "hit@1": hit1, "hit@3": hit3, "top_score": top_score})
    ctx.show_data("Results", rows)
    ctx.note(f"hit@1 = {hits1}/{scored}, hit@3 = {hits3}/{scored}")
    ctx.note(f"The unanswerable question still scores {rows[-1]['top_score']}: a score cutoff alone cannot catch it, so the prompt must (script 2).")
    ctx.note("If hit@3 is low, fix retrieval first: chunk size, overlap, k, or the embedding model. Prompts cannot add missing chunks.")


if __name__ == "__main__":
    main()
