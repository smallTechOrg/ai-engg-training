"""06.4/2  Embeddings, a vector store and a retriever

LangChain's retrieval pieces and what each does:

  Embeddings          an interface: embed_documents(list) and embed_query(text). We write a 6-line class that
                      calls `ctx.embed` (local model, or a hosted one if EMBEDDING_MODEL is set).
  VectorStore         holds chunks plus their vectors. `InMemoryVectorStore` ships with langchain-core.
  Retriever           `store.as_retriever(search_kwargs={"k": 3})`: a Runnable, text in, list of Documents out.

You built the same trio by hand in lessons 03.1 and 04.1 (numpy matrix, cosine, argsort). No chat model here.

Run it:   ./run 06.4/2          (Windows: run 06.4/2)
"""

import warnings
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
QUERIES = ["I can't print, the printer says offline", "How long until my laptop gets replaced?", "What is the parental leave policy?"]


def load_chunks():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from langchain_community.document_loaders import TextLoader
    docs = []
    for path in sorted(KB_DIR.glob("*.md")):
        for d in TextLoader(str(path), encoding="utf-8").load():
            d.metadata["source"] = path.name
            docs.append(d)
    return RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=60).split_documents(docs)


@lesson("06.4/2", "Embeddings, vector store, retriever")
def main(ctx):
    class LabEmbeddings(Embeddings):
        """The LangChain Embeddings interface over the course's embedding helper."""

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return ctx.embed(texts)

        def embed_query(self, text: str) -> list[float]:
            return ctx.embed([text])[0]

    ctx.step("Index the knowledge base")
    chunks = load_chunks()
    store = InMemoryVectorStore(embedding=LabEmbeddings())
    ids = store.add_documents(chunks)
    ctx.note(f"{len(chunks)} chunks embedded in one batch and stored ({len(ids)} ids returned).")
    ctx.note("With a hosted provider you would use langchain_openai.OpenAIEmbeddings(model=..., base_url=..., api_key=...) here instead.")

    ctx.step("Search with scores")
    for query in QUERIES:
        results = store.similarity_search_with_score(query, k=2)
        ctx.show_data(query, [{"score": round(score, 2), "source": doc.metadata["source"], "text": doc.page_content[:70] + "..."} for doc, score in results])
    ctx.note("The unrelated question still gets its 'nearest' chunks: scores are relative, never a yes/no (lesson 04.1).")

    ctx.step("The retriever: the same search as a Runnable")
    retriever = store.as_retriever(search_kwargs={"k": 3})
    docs = retriever.invoke(QUERIES[1])
    ctx.show_data(f"retriever.invoke({QUERIES[1]!r})", [{"source": d.metadata["source"], "text": d.page_content[:60] + "..."} for d in docs])
    batch = retriever.batch(QUERIES[:2])
    ctx.note(f"retriever.batch(...) gave {[len(b) for b in batch]} documents per query; it chains with | like everything else (script 3).")
    ctx.note("Swapping the store (Chroma, pgvector...) changes one line; the retriever interface stays the same.")


if __name__ == "__main__":
    main()
