"""06.1/2  LCEL: prompt | model | parser

LangChain Expression Language (LCEL) chains Runnables with the `|` operator. Each piece
takes the previous piece's output as its input:

    ChatPromptTemplate  ->  ChatOpenAI  ->  StrOutputParser
    dict of variables      PromptValue      AIMessage            str

The result is itself a Runnable, so one chain gives you invoke, batch and stream.

Run it:   ./run 06.1/2          (Windows: run 06.1/2)
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from labkit import lesson

PRODUCTS = ["a VPN", "multi-factor authentication", "a password manager"]


@lesson("06.1/2", "LCEL: prompt | model | parser")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    ctx.step("Build the chain, one piece at a time")
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You explain IT topics to non-technical employees in one short sentence."),
            ("human", "What is {topic}?"),
        ]
    )
    parser = StrOutputParser()
    chain = prompt | model | parser
    ctx.show_data("The pieces", {"prompt": type(prompt).__name__, "model": type(model).__name__, "parser": type(parser).__name__, "chain": type(chain).__name__})
    ctx.note("prompt | model | parser builds a RunnableSequence. Nothing has been sent to the model yet.")

    ctx.step("What each runnable passes on")
    variables = {"topic": PRODUCTS[0]}
    prompt_value = prompt.invoke(variables)
    ctx.show_data("1. prompt.invoke(dict) -> " + type(prompt_value).__name__, [f"{type(m).__name__}: {m.content}" for m in prompt_value.to_messages()])
    ai_message = model.invoke(prompt_value)
    ctx.show_data("2. model.invoke(prompt_value) -> " + type(ai_message).__name__, {"content": ai_message.content, "usage_metadata": ai_message.usage_metadata})
    if ai_message.usage_metadata:
        ctx.record_usage(ai_message.usage_metadata)
    text = parser.invoke(ai_message)
    ctx.show_data("3. parser.invoke(ai_message) -> " + type(text).__name__, text)
    ctx.note("The chain does these three steps for you. To debug a chain, check what each step outputs.")

    ctx.step("invoke: the whole chain, one input")
    result = chain.invoke(variables)
    ctx.show_data("chain.invoke({'topic': ...})", result)

    ctx.step("batch: several inputs, run concurrently")
    results = chain.batch([{"topic": p} for p in PRODUCTS])
    for product, answer in zip(PRODUCTS, results):
        ctx.show_data(f"chain.batch -> {product}", answer)
    ctx.note("batch returns a list in input order. You cannot see token usage here: the parser dropped the AIMessage.")

    ctx.step("stream: the answer piece by piece")
    pieces = []
    for piece in chain.stream({"topic": PRODUCTS[1]}):
        pieces.append(piece)
    ctx.show_data("chain.stream yielded", {"number of pieces": len(pieces), "first pieces": pieces[:5], "joined": "".join(pieces)})
    ctx.note("Each piece is a str because the string parser comes last. Without it you would get AIMessageChunk objects.")


if __name__ == "__main__":
    main()
