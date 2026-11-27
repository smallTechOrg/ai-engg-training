"""06.5/3  Capstone step 3: a conversation that remembers and still grounds its answers

A follow-up such as "And on my phone?" is useless as a search query. The standard fix is a
**condense step**: rewrite the follow-up plus the chat history into one standalone question, retrieve
with THAT, and answer from the retrieved chunks.

    history + follow-up  ->  condense chain  ->  standalone question  ->  retriever  ->  answer chain

The history is a plain list of messages here (lesson 06.3 script 1). Swap it for a LangGraph checkpointer
(06.3 scripts 2-3) when you need sessions or persistence. The script prints the rewritten question on each turn.

Run it:   ./run 06.5/3          (Windows: run 06.5/3)
"""

import warnings
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
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


TURNS = [
    "How do I get the VPN working on my laptop?",
    "And what if it still will not connect?",
    "How long until it drops the connection by itself?",
]
MAX_HISTORY = 6  # messages kept for the condense step


@lesson("06.5/3", "Capstone 3: conversational RAG")
def main(ctx):
    store, chunks = build_store(ctx)
    retriever = store.as_retriever(search_kwargs={"k": 3})
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    condense_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Rewrite the user's last message as one standalone search question, using the chat history to resolve words like 'it' or 'that'. Reply with the question only."),
            MessagesPlaceholder("history"),
            ("human", "{question}"),
        ]
    )
    answer_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the IT helpdesk assistant at Larkspur Labs. Answer ONLY from the context, in at most three sentences, "
                "citing files like [vpn.md]. If the context lacks the answer, say you don't know and suggest the helpdesk.",
            ),
            MessagesPlaceholder("history"),
            ("human", "Context:\n\n{context}\n\nQuestion: {question}"),
        ]
    )
    condense = condense_prompt | model | StrOutputParser()
    answer = answer_prompt | model | StrOutputParser()

    ctx.step("A three-turn conversation")
    history: list = []
    for turn, question in enumerate(TURNS, start=1):
        recent = history[-MAX_HISTORY:]
        standalone = condense.invoke({"history": recent, "question": question}) if recent else question
        docs = retriever.invoke(standalone)
        context = "\n\n".join(f"[{d.metadata['source']}]\n{d.page_content}" for d in docs)
        reply = answer.invoke({"history": recent, "context": context, "question": question})
        ctx.show_data(f"Turn {turn}: {question}", {"standalone_question": standalone, "sources": list(dict.fromkeys(d.metadata["source"] for d in docs)), "answer": reply})
        history += [HumanMessage(question), AIMessage(reply)]

    ctx.step("What to take away")
    ctx.note("Turn 1 skips the condense call (no history). Later turns cost two model calls: rewrite, then answer.")
    ctx.note("Compare the standalone question with the raw follow-up: retrieval ran on the rewritten one.")
    ctx.note(f"Only the last {MAX_HISTORY} messages feed the rewrite; answers are grounded in retrieved text, not in history.")
    ctx.note("Token counts are not shown: StrOutputParser drops the AIMessage (see 06.1).")


if __name__ == "__main__":
    main()
