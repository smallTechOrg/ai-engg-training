"""06.3/1  Memory is just a message list: with and without history

A chat model remembers nothing between calls. "Memory" means: store the earlier messages and
send them again. The prompt has a `MessagesPlaceholder` slot to receive them.

This script does it BY HAND, with a plain Python list, so the next script's automation is no mystery:
  1. ask a follow-up with no history  -> the model cannot know what "it" is
  2. keep the history yourself and pass it in the placeholder -> it can

(LangChain 1.x deprecates its older history classes such as InMemoryChatMessageHistory and
RunnableWithMessageHistory in favour of LangGraph persistence, which is script 2.)

Run it:   ./run 06.3/1          (Windows: run 06.3/1)
"""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from labkit import lesson

TURNS = [
    "Hi, I'm Priya. My laptop has no sound after the update.",
    "I already restarted it. What else can I try?",
    "What was my name again, and what was the problem?",
]


@lesson("06.3/1", "Memory is just a message list")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are the IT helpdesk assistant at Larkspur Labs. Answer in at most two sentences."),
            MessagesPlaceholder("history"),
            ("human", "{question}"),
        ]
    )
    chain = prompt | model

    ctx.step("No memory: each call stands alone")
    reply = chain.invoke({"history": [], "question": TURNS[2]})
    ctx.record_usage(reply.usage_metadata)
    ctx.show_data("Asked cold: " + TURNS[2], reply.content)

    ctx.step("Memory by hand: a list you append to")
    history: list = []
    for question in TURNS:
        reply = chain.invoke({"history": history, "question": question})
        ctx.record_usage(reply.usage_metadata)
        history += [HumanMessage(question), AIMessage(reply.content)]
        ctx.show_data(f"[{len(history)} messages stored] {question}", reply.content)

    ctx.step("What the model saw on the last turn")
    sent = prompt.invoke({"history": history[:-2], "question": TURNS[2]}).to_messages()
    ctx.show_data("messages sent", [f"{m.type}: {str(m.content)[:70]}" for m in sent])
    ctx.note("Every turn re-sends the whole history, so tokens per call grow with the conversation (script 3 caps that).")
    ctx.note("You also own the bookkeeping: one list per conversation, saved somewhere, trimmed somewhere. Script 2 hands that to LangGraph.")


if __name__ == "__main__":
    main()
