"""08.1/2  A model node and a reducer for messages

Two things are new:

  1. a REDUCER. Normally a node's return value REPLACES a field. A field annotated with a
     reducer is COMBINED instead: `Annotated[list, add_messages]` appends new messages to
     the list (and updates one in place if it has the same id);
  2. a MODEL NODE: an ordinary node whose function calls a chat model (LangChain's
     ChatOpenAI, pointed at your endpoint) and returns the reply as a new message.

Run it:   ./run 08.1/2          (Windows: run 08.1/2)
"""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from labkit import lesson


def as_dicts(messages):
    """LangChain message objects -> the role/content dicts that ctx.show_messages prints."""
    roles = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
    return [{"role": roles.get(m.type, m.type), "content": m.content} for m in messages]


# --- Part 1: what a reducer changes, without a model -------------------------------


class Overwrite(TypedDict):
    notes: list[str]  # no reducer: the last write wins


class Accumulate(TypedDict):
    notes: Annotated[list[str], operator.add]  # reducer: old + new


def run_two_writers(state_type):
    builder = StateGraph(state_type)
    builder.add_node("first", lambda state: {"notes": ["written by first"]})
    builder.add_node("second", lambda state: {"notes": ["written by second"]})
    builder.add_edge(START, "first")
    builder.add_edge("first", "second")
    builder.add_edge("second", END)
    return builder.compile().invoke({"notes": ["from the input"]})


# --- Part 2: a chat graph with a model node -----------------------------------------


class ChatState(TypedDict, total=False):
    ticket: str  # plain field: the ticket text as it arrived
    messages: Annotated[list, add_messages]  # reducer field: the conversation
    model_calls: int


SYSTEM_PROMPT = "You are the IT helpdesk assistant at Larkspur Labs. Answer in at most two sentences."


@lesson("08.1/2", "A model node and a reducer for messages")
def main(ctx):
    ctx.step("Without a reducer, a node's return value replaces the field")
    ctx.show_data("notes after first -> second", run_two_writers(Overwrite)["notes"])

    ctx.step("With a reducer, the values are combined")
    ctx.note("Annotated[list[str], operator.add] tells LangGraph: new value = old value + returned value.")
    ctx.show_data("notes after first -> second", run_two_writers(Accumulate)["notes"])

    ctx.step("Build a graph whose state is a conversation")
    ctx.note("messages: Annotated[list, add_messages] -- the reducer LangGraph ships for chat history.")
    llm = ChatOpenAI(
        model=ctx.model,
        base_url=ctx.settings.base_url,
        api_key=ctx.settings.api_key,
        temperature=0,
    )

    def frame(state: ChatState) -> dict:
        # A plain node: turns the ticket into the opening messages. add_messages appends them.
        return {"messages": [SystemMessage(SYSTEM_PROMPT), HumanMessage(state["ticket"])], "model_calls": 0}

    def assistant(state: ChatState) -> dict:
        # The model node: send the whole conversation, return only the new reply.
        reply = llm.invoke(state["messages"])
        ctx.record_usage(reply.usage_metadata)
        return {"messages": [reply], "model_calls": state["model_calls"] + 1}

    builder = StateGraph(ChatState)
    builder.add_node("frame", frame)
    builder.add_node("assistant", assistant)
    builder.add_edge(START, "frame")
    builder.add_edge("frame", "assistant")
    builder.add_edge("assistant", END)
    graph = builder.compile()
    ctx.console.print(graph.get_graph().draw_mermaid(), markup=False, highlight=False)

    ctx.step("Run it and watch the messages grow")
    state = {"ticket": "Ticket #5110: How do I connect to the office printer from my laptop?"}
    ctx.show_data("Input state", state)
    ctx.note('stream_mode=["updates", "values"] yields both what each node returned and the full state after it.')
    final = None
    for mode, data in graph.stream(state, stream_mode=["updates", "values"]):
        if mode == "values":
            final = data  # the whole state so far; the last one is the final state
            continue
        for node, changes in data.items():
            ctx.console.print(f"[bold]after node '{node}'[/bold] returned {len(changes['messages'])} new message(s)")
            ctx.show_messages(as_dicts(changes["messages"]), label="  returned")

    ctx.step("Read the final state")
    ctx.note(f"messages holds {len(final['messages'])} entries: the reducer appended each node's messages in turn.")
    ctx.show_messages(as_dicts(final["messages"]), label="Final state: messages")
    last = final["messages"][-1]
    ctx.note(f"The last one is an {type(last).__name__}; model_calls = {final['model_calls']}.")
    if not isinstance(last, AIMessage) or not last.content:
        ctx.note("The model returned an empty reply. The graph still finished; the state shows exactly what came back.")

    ctx.step("What the framework did for you")
    ctx.note("By hand (module 01) you kept a messages list and appended each reply yourself.")
    ctx.note("Here the reducer does the appending, so every node just returns what it adds.")
    ctx.note("graph.invoke(state) would return the same final state without the step-by-step view.")


if __name__ == "__main__":
    main()
