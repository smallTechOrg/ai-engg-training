"""08.3/1  Streaming modes

graph.stream() can report a run in different ways, chosen with stream_mode:

  values   the WHOLE state after every step
  updates  only what each node returned (08.1 used this)
  custom   anything a node chooses to emit with get_stream_writer(): progress messages
  messages (token, metadata) pairs: the model's reply as it is generated, token by token

You can ask for several at once; each item then arrives as (mode, data).

Run it:   ./run 08.3/1          (Windows: run 08.3/1)
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from labkit import lesson

TICKET = "Ticket #5301: how do I request a second monitor for my desk?"


class State(TypedDict, total=False):
    ticket: str
    cleaned: str
    answer: str


@lesson("08.3/1", "Streaming modes")
def main(ctx):
    llm = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    def clean(state: State) -> dict:
        writer = get_stream_writer()  # only works inside a node, while a run is streaming
        writer({"progress": "cleaning the ticket text"})
        return {"cleaned": " ".join(state["ticket"].split())}

    def answer(state: State) -> dict:
        writer = get_stream_writer()
        writer({"progress": "asking the model"})
        reply = llm.invoke(
            [("system", "You are the Larkspur Labs IT helpdesk. Answer in one sentence."), ("human", state["cleaned"])]
        )
        ctx.record_usage(reply.usage_metadata)
        return {"answer": str(reply.content).strip()}

    builder = StateGraph(State)
    builder.add_node("clean", clean)
    builder.add_node("answer", answer)
    builder.add_edge(START, "clean")
    builder.add_edge("clean", "answer")
    builder.add_edge("answer", END)
    graph = builder.compile()

    ctx.step('stream_mode="values": the whole state after each step')
    for state in graph.stream({"ticket": TICKET}, stream_mode="values"):
        ctx.note(f"state now has fields: {', '.join(state)}")

    ctx.step('stream_mode="updates": only what each node returned')
    for update in graph.stream({"ticket": TICKET}, stream_mode="updates"):
        for node, changes in update.items():
            ctx.note(f"{node} wrote: {', '.join(changes)}")

    ctx.step('stream_mode="custom": progress messages a node emits itself')
    ctx.note("Inside a node, get_stream_writer() returns a function; whatever you pass appears in the stream.")
    for item in graph.stream({"ticket": TICKET}, stream_mode="custom"):
        ctx.show_data("custom event", item)

    ctx.step('stream_mode="messages": the model reply token by token')
    ctx.note("LangGraph taps the chat model inside the node, so you get chunks while the node is still running.")
    chunks = 0
    text = ""
    for token, metadata in graph.stream({"ticket": TICKET}, stream_mode="messages"):
        if metadata.get("langgraph_node") == "answer" and token.content:
            chunks += 1
            text += str(token.content)
    ctx.note(f"{chunks} chunk(s) from node 'answer' joined to: {text.strip()!r}")
    if chunks == 0:
        ctx.note("No chunks arrived: this endpoint may not stream. The run still finished.")

    ctx.step("Several modes at once")
    for mode, data in graph.stream({"ticket": TICKET}, stream_mode=["updates", "custom"]):
        ctx.note(f"[{mode}] {list(data) if mode == 'updates' else data}")

    ctx.step("Which mode when?")
    ctx.note("values: simple dashboards and debugging. updates: audit logs. custom: progress bars. messages: chat UIs.")


if __name__ == "__main__":
    main()
