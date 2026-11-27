"""06.3/2  Sessions: a LangGraph graph with a checkpointer

LangChain 1.x's answer to "give my chain memory" is LangGraph persistence:

  - a graph whose state is `MessagesState` (a list of messages that new messages are APPENDED to)
  - one node that calls the model with the state's messages
  - `compile(checkpointer=InMemorySaver())`: after every step the state is saved under a `thread_id`

You call `graph.invoke({"messages": [new human message]}, config={"configurable": {"thread_id": ...}})`
and the saver loads the earlier messages for that thread first. Two thread ids are two separate
conversations. This is the same idea as script 1's list, with the storing and loading done for you.
Module 08 and 09 go much deeper into LangGraph; here it is only a memory holder.

Run it:   ./run 06.3/2          (Windows: run 06.3/2)
"""

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from labkit import lesson


@lesson("06.3/2", "Sessions with a LangGraph checkpointer")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are the IT helpdesk assistant at Larkspur Labs. Answer in at most two sentences."),
            MessagesPlaceholder("messages"),
        ]
    )
    chain = prompt | model

    ctx.step("Build the graph")

    def chat_node(state: MessagesState):
        reply = chain.invoke({"messages": state["messages"]})
        ctx.record_usage(reply.usage_metadata, quiet=True)
        return {"messages": [reply]}  # appended to the state, not replacing it

    builder = StateGraph(MessagesState)
    builder.add_node("chat", chat_node)
    builder.add_edge(START, "chat")
    builder.add_edge("chat", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    ctx.note("START -> chat -> END, state = list of messages, saver = InMemorySaver (lost when the process ends).")

    def say(thread_id, question):
        result = graph.invoke({"messages": [HumanMessage(question)]}, config={"configurable": {"thread_id": thread_id}})
        ctx.show_data(f"[{thread_id}] {question}", result["messages"][-1].content)

    ctx.step("Two employees, interleaved")
    say("priya", "Hi, I'm Priya. My monitor flickers when I plug in the dock.")
    say("tom", "Hi, I'm Tom. I need access to the finance shared drive.")
    say("priya", "Which of my devices did I say had the problem?")
    say("tom", "Who am I and what did I ask for?")

    ctx.step("Look inside each thread's saved state")
    for thread_id in ("priya", "tom"):
        snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
        ctx.show_data(f"thread {thread_id}", [f"{m.type}: {str(m.content)[:60]}" for m in snapshot.values["messages"]])
    ctx.note("The second Priya question was answered from HER thread only. A new thread_id starts fresh.")
    ctx.note("Same API for every saver: swap InMemorySaver for a SQLite or Postgres saver and memory survives restarts (script 3).")


if __name__ == "__main__":
    main()
