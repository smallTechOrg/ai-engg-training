"""09.2/2  A reviewer approves or rejects a model draft

The model drafts a reply; the graph pauses for a human; a rejection carries feedback back
to the model for another draft (a cycle, as in 09.1, but the checker is a person). The
"person" here is a scripted list of decisions so the lesson runs unattended. In a real app
the decision would come from a button in the UI, a Slack message or an email link.

Run it:   ./run 09.2/2          (Windows: run 09.2/2)
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from labkit import lesson

MAX_REJECTIONS = 2  # after this many rejections the draft goes to a human agent instead
# What the reviewer "types", in order. Edit this to try other paths.
SCRIPTED_DECISIONS = [
    {"action": "reject", "feedback": "Too wordy. Two sentences, and name the ticket id."},
    {"action": "approve"},
]


class State(TypedDict):
    ticket: str
    draft: str
    feedback: str
    rejections: int
    outcome: str


@lesson("09.2/2", "Approve or reject a draft")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0.3)

    def draft(state: State) -> dict:
        prompt = state["ticket"]
        if state["feedback"]:
            prompt += f"\n\nYour previous draft:\n{state['draft']}\n\nThe reviewer rejected it: {state['feedback']}\nWrite a better one."
        ai = model.invoke([("system", "You write short, friendly IT helpdesk replies for Larkspur Labs."), ("user", prompt)])
        ctx.record_usage(ai.usage_metadata)
        return {"draft": str(ai.content)}

    def review(state: State) -> dict:
        decision = interrupt({"draft": state["draft"], "options": ["approve", "reject"]})
        if decision.get("action") == "approve":
            return {"outcome": "approved", "feedback": ""}
        return {"outcome": "rejected", "feedback": decision.get("feedback", ""), "rejections": state["rejections"] + 1}

    def route(state: State) -> str:
        if state["outcome"] == "approved":
            return "send"
        if state["rejections"] >= MAX_REJECTIONS:
            return "escalate"
        return "draft"

    def send(state: State) -> dict:
        return {"outcome": "sent to the employee"}

    def escalate(state: State) -> dict:
        return {"outcome": f"escalated to a human agent after {state['rejections']} rejections"}

    ctx.step("Build: draft -> review (interrupt) -> send | draft again | escalate")
    g = StateGraph(State)
    for name, fn in [("draft", draft), ("review", review), ("send", send), ("escalate", escalate)]:
        g.add_node(name, fn)
    g.add_edge(START, "draft")
    g.add_edge("draft", "review")
    g.add_conditional_edges("review", route, ["send", "draft", "escalate"])
    g.add_edge("send", END)
    g.add_edge("escalate", END)
    graph = g.compile(checkpointer=InMemorySaver())

    ctx.step("Run, answering each interrupt from the scripted decisions")
    config = {"configurable": {"thread_id": "LL-2060"}, "recursion_limit": 20}
    result = graph.invoke({"ticket": "Employee asks: my VPN token reset (ticket LL-2060) is done, what now?",
                           "draft": "", "feedback": "", "rejections": 0, "outcome": ""}, config)
    decisions = iter(SCRIPTED_DECISIONS)
    pauses = 0
    while "__interrupt__" in result:
        pauses += 1
        payload = result["__interrupt__"][0].value
        ctx.note(f"[pause {pauses}] draft awaiting review: {payload['draft'][:160]}")
        decision = next(decisions, {"action": "reject", "feedback": "(script ran out of decisions)"})
        ctx.note(f"[reviewer] {decision}")
        if pauses >= 6:  # hard cap on the resume loop itself
            ctx.note("Stopping: 6 pauses is the cap for this script.")
            break
        result = graph.invoke(Command(resume=decision), config)

    ctx.step("Result")
    ctx.note(f"pauses: {pauses}, rejections: {graph.get_state(config).values['rejections']}")
    ctx.note(f"outcome: {graph.get_state(config).values['outcome']}")
    ctx.note("Each rejection re-ran 'draft' with the feedback; each pause was one interrupt() on the same thread.")


if __name__ == "__main__":
    main()
