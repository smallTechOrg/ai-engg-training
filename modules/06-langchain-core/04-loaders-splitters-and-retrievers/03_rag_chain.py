"""06.4/3  Scenario: the RAG chain in LCEL

    question -> retriever -> format the chunks -> prompt -> model -> parser

Written as one LCEL expression. `RunnablePassthrough` carries the question forward while the retriever
fetches context in parallel (a dict of runnables is a RunnableParallel). Four questions go through it,
one of which the knowledge base cannot answer, to check the prompt's "I don't know" rule still holds.

Compare lesson 04.1 script 3: same pipeline, but there it was ~40 lines of loops. Here each stage is a named, swappable piece.

Run it:   ./run 06.4/3          (Windows: run 06.4/3)
"""

import warnings
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
QUESTIONS = [
    "I forgot my password, how do I get back in?",
    "The printer on my floor is offline, what should I try?",
    "When do new starters collect their laptop?",
    "What is the company's parental leave policy?",  # not in the KB on purpose
]


@lesson("06.4/3", "Scenario: the RAG chain")
def main(ctx):
    class LabEmbeddings(Embeddings):
        def embed_documents(self, texts):
            return ctx.embed(texts)

        def embed_query(self, text):
            return ctx.embed([text])[0]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from langchain_community.document_loaders import TextLoader
    docs = []
    for path in sorted(KB_DIR.glob("*.md")):
        for d in TextLoader(str(path), encoding="utf-8").load():
            d.metadata["source"] = path.name
            docs.append(d)
    chunks = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=60).split_documents(docs)
    retriever = InMemoryVectorStore.from_documents(chunks, LabEmbeddings()).as_retriever(search_kwargs={"k": 3})

    def format_docs(documents):
        return "\n\n".join(f"[{d.metadata['source']}]\n{d.page_content}" for d in documents)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the IT helpdesk assistant at Larkspur Labs. Answer ONLY from the context. "
                "Cite the file name in square brackets, like [vpn.md]. "
                'If the context does not contain the answer, say exactly: "I don\'t know based on the IT knowledge base." and suggest contacting the helpdesk.',
            ),
            ("human", "Context:\n\n{context}\n\nQuestion: {question}"),
        ]
    )
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    ctx.step("Assemble the chain")
    chain = {"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt | model | StrOutputParser()
    ctx.note('{"context": retriever | format_docs, "question": RunnablePassthrough()} | prompt | model | StrOutputParser()')
    ctx.note(f"{len(chunks)} chunks indexed. The dict at the front runs both branches on the same input string.")

    ctx.step("What the model receives for the first question")
    rendered = prompt.invoke({"context": format_docs(retriever.invoke(QUESTIONS[0])), "question": QUESTIONS[0]}).to_messages()
    ctx.show_messages([{"role": m.type.replace("human", "user"), "content": m.content} for m in rendered])

    ctx.step("Ask four questions (one batch)")
    answers = chain.batch(QUESTIONS)
    for question, answer in zip(QUESTIONS, answers):
        ctx.show_data(question, answer)
        if "don't know" in answer.lower() or "do not know" in answer.lower():
            ctx.note("-> declined: the retrieved chunks did not hold the answer.")
    ctx.note("The sources are only visible inside the prompt here. The capstone returns them next to the answer.")
    ctx.note("Token counts are not shown: StrOutputParser drops the AIMessage (see 06.1).")


if __name__ == "__main__":
    main()
