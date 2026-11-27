"""06.3/3  Scenario: a helpdesk chat with bounded, persistent memory

Two production problems with script 2's memory:

  1. It grows without limit, so cost and latency climb each turn. Fix: `trim_messages` keeps only the
     last few messages in what the model SEES (the saved state keeps everything).
  2. It vanishes when the process ends. Fix: a SQLite saver (`SqliteSaver`), here in a temp directory.

The script "restarts" the app between turns 2 and 3 by building a brand-new graph and a new
database connection over the same file: the conversation is still there.

Run it:   ./run 06.3/3          (Windows: run 06.3/3)
"""

import sqlite3
import tempfile
from pathlib import Path

from langchain_core.messages import HumanMessage, trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from labkit import lesson

KEEP_LAST = 4  # messages the model sees, not messages stored
THREAD = {"configurable": {"thread_id": "priya"}}


@lesson("06.3/3", "Scenario: bounded, persistent helpdesk memory")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    db_path = Path(tempfile.mkdtemp(prefix="larkspur-chat-")) / "memory.sqlite"
    sent_sizes: list[int] = []  # how many messages the model saw per call (including the new question)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are the IT helpdesk assistant at Larkspur Labs. Answer in at most two sentences."),
            MessagesPlaceholder("messages"),
        ]
    )
    chain = prompt | model

    def chat_node(state: MessagesState):
        window = trim_messages(
            state["messages"], strategy="last", token_counter=len, max_tokens=KEEP_LAST, start_on="human", include_system=False
        )
        sent_sizes.append(len(window))
        reply = chain.invoke({"messages": window})
        ctx.record_usage(reply.usage_metadata, quiet=True)
        return {"messages": [reply]}

    def build_graph():
        """A fresh graph over a fresh connection to the same file: what an app restart does."""
        connection = sqlite3.connect(db_path, check_same_thread=False)
        builder = StateGraph(MessagesState)
        builder.add_node("chat", chat_node)
        builder.add_edge(START, "chat")
        builder.add_edge("chat", END)
        return builder.compile(checkpointer=SqliteSaver(connection)), connection

    def say(graph, question):
        result = graph.invoke({"messages": [HumanMessage(question)]}, config=THREAD)
        ctx.show_data(question, result["messages"][-1].content)

    ctx.step(f"A chat whose model sees at most the last {KEEP_LAST} messages")
    graph, connection = build_graph()
    say(graph, "Hi, I'm Priya. My laptop has no sound after the update.")
    say(graph, "I already restarted it. What else can I try?")
    connection.close()

    ctx.step("Restart the app: a new graph and connection over the same file")
    graph, connection = build_graph()
    say(graph, "Remind me: what was the problem I reported?")
    say(graph, "Thanks. Now my headset mic is quiet too.")
    say(graph, "Should I raise a ticket for both?")

    ctx.step("Stored versus seen")
    stored = graph.get_state(THREAD).values["messages"]
    connection.close()
    ctx.show_data("messages stored in the database", len(stored))
    ctx.show_data("messages the model saw per call", sent_sizes)
    ctx.note(f"The window is {KEEP_LAST} messages but start_on='human' drops a leading AI message, so the model saw 3 once the chat was long.")
    ctx.note("Storage keeps the whole conversation (audit, support hand-over); the window keeps each call cheap.")
    ctx.note("Trimming loses facts: once the first turn left the window, 'Priya' was gone. Fixes: summarise old turns, or save key facts separately (module 13).")


if __name__ == "__main__":
    main()
