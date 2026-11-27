"""09.3/2  Threads, history and forking with a chat model

With a checkpointer, `thread_id` IS the memory: call the graph again with the same
thread_id and the earlier messages are already in the state. Every step is a numbered
checkpoint, so you can list the history and branch from an earlier one ("time travel"):
run again from that point with new input to create a branch. Nothing is overwritten:
the old checkpoints stay in the history.

Run it:   ./run 09.3/2          (Windows: run 09.3/2)
"""

import tempfile
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from labkit import lesson


def show_thread(ctx, graph, config, label):
    msgs = graph.get_state(config).values.get("messages", [])
    ctx.note(f"{label} holds {len(msgs)} message(s):")
    for m in msgs:
        ctx.note(f"    {m.type:>5}: {str(m.content)[:90]}")


@lesson("09.3/2", "Threads, history and forking")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    def chat(state: MessagesState) -> dict:
        ai = model.invoke([("system", "You are a terse IT helpdesk assistant for Larkspur Labs. One or two sentences.")] + state["messages"])
        ctx.record_usage(ai.usage_metadata)
        return {"messages": [ai]}

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        with SqliteSaver.from_conn_string(str(Path(tmp) / "chat.sqlite")) as saver:
            g = StateGraph(MessagesState)
            g.add_node("chat", chat)
            g.add_edge(START, "chat")
            g.add_edge("chat", END)
            graph = g.compile(checkpointer=saver)

            ctx.step("Thread A: two turns, the second relies on the first")
            a = {"configurable": {"thread_id": "priya"}}
            graph.invoke({"messages": [HumanMessage("Hi, I am Priya and my laptop is a ThinkPad X1.")]}, a)
            graph.invoke({"messages": [HumanMessage("Which laptop did I say I have?")]}, a)
            show_thread(ctx, graph, a, "thread 'priya'")

            ctx.step("Thread B: a different thread_id knows nothing about A")
            b = {"configurable": {"thread_id": "marco"}}
            graph.invoke({"messages": [HumanMessage("Which laptop did I say I have?")]}, b)
            show_thread(ctx, graph, b, "thread 'marco'")

            ctx.step("List thread A's checkpoints (newest first)")
            history = list(graph.get_state_history(a))
            for snap in history:
                ctx.note(f"step {snap.metadata.get('step'):>2}  messages={len(snap.values.get('messages', []))}  next={snap.next}")

            ctx.step("Fork: go back to just after turn 1 and ask something else")
            after_turn_1 = next(s for s in history if len(s.values.get("messages", [])) == 2 and not s.next)
            ctx.note(f"chosen checkpoint: step {after_turn_1.metadata.get('step')}, {len(after_turn_1.values['messages'])} messages")
            ctx.note("Running from an OLD checkpoint's config with new input creates a branch; nothing is overwritten.")
            graph.invoke({"messages": [HumanMessage("Never mind. How do I reset my VPN token?")]}, after_turn_1.config)
            show_thread(ctx, graph, a, "thread 'priya' now (latest checkpoint = the branch)")

            ctx.step("The old checkpoints are still there")
            show_thread(ctx, graph, after_turn_1.config, "the checkpoint we branched from")
            ctx.note(f"checkpoints in the thread now: {len(list(graph.get_state_history(a)))} (was {len(history)}); the branch added to the history")
            ctx.note("update_state(config, values) writes a hand-made checkpoint the same way: the tool for a reviewer who corrects the state.")

    ctx.note("Forking is how you replay a failure with a different input, or let a reviewer correct a state and carry on.")


if __name__ == "__main__":
    main()
