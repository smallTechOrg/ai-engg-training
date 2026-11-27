"""06.5/2  Capstone step 2: the RAG chain that returns its sources

The answer alone is not enough for a helpdesk: staff and auditors want to know WHICH knowledge-base
files it came from. The chain keeps the retrieved documents next to the answer:

    {"question", "docs"}  ->  .assign(answer = prompt | model | parser)  ->  {"question", "docs", "answer"}

`RunnableParallel(...).assign(...)` adds keys instead of replacing the input, so nothing is lost on the way.
The script then checks each answer against the acceptance criteria listed in the README.

Run it:   ./run 06.5/2          (Windows: run 06.5/2)
"""

import warnings
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_openai import ChatOpenAI

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


# (question, expected source, or None when the KB cannot answer)
CASES = [
    ("I forgot my password, how do I get back in?", "passwords.md"),
    ("Who approves software that costs more than 200 pounds a year?", "software.md"),
    ("When do new starters collect their laptop?", "onboarding.md"),
    ("What is the company's parental leave policy?", None),
]
DONT_KNOW = "I don't know based on the IT knowledge base."


@lesson("06.5/2", "Capstone 2: RAG chain with sources")
def main(ctx):
    store, chunks = build_store(ctx)
    retriever = store.as_retriever(search_kwargs={"k": 3})
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the IT helpdesk assistant at Larkspur Labs. Answer ONLY from the context, in at most three sentences. "
                "Cite each file you used in square brackets, like [vpn.md]. "
                f'If the context does not contain the answer, reply exactly: "{DONT_KNOW}" and suggest contacting the helpdesk.',
            ),
            ("human", "Context:\n\n{context}\n\nQuestion: {question}"),
        ]
    )

    def format_docs(inputs):
        return "\n\n".join(f"[{d.metadata['source']}]\n{d.page_content}" for d in inputs["docs"])

    ctx.step("Assemble the chain")
    answer_chain = RunnablePassthrough.assign(context=format_docs) | prompt | model | StrOutputParser()
    chain = RunnableParallel(question=RunnablePassthrough(), docs=retriever).assign(answer=answer_chain)
    ctx.note("RunnableParallel(question=..., docs=retriever).assign(answer=...) returns a dict with all three keys.")
    ctx.note(f"{len(chunks)} chunks indexed.")

    ctx.step("Ask, then check the acceptance criteria")
    results = chain.batch([q for q, _ in CASES])
    table = []
    for (question, expected), result in zip(CASES, results):
        answer = result["answer"]
        retrieved = list(dict.fromkeys(d.metadata["source"] for d in result["docs"]))
        cited = [s for s in retrieved if f"[{s}]" in answer or s in answer]
        declined = "don't know" in answer.lower() or "do not know" in answer.lower()
        if expected is None:
            ok, why = declined, "declined to answer"
        else:
            ok, why = (expected in cited and not declined), f"cites {expected}"
        ctx.show_data(question, {"answer": answer, "retrieved_sources": retrieved, "cited": cited})
        table.append((question[:48], "PASS" if ok else "CHECK", why))
    ctx.step("Summary")
    for question, verdict, why in table:
        ctx.note(f"{verdict:5} {question:50} ({why})")
    ctx.note("CHECK means look at the answer, not that the chain is broken: models cite in many styles.")
    ctx.note("Token counts are not shown: StrOutputParser drops the AIMessage (see 06.1).")


if __name__ == "__main__":
    main()
