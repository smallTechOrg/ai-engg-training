"""08.1/3  Scenario: a three-step helpdesk workflow

Classify a ticket, draft a reply, polish the reply: a linear graph where each node is one
model call and the state carries the work from step to step. You will see the state grow
after every node, which is the point of using a graph for a workflow.

Run it:   ./run 08.1/3          (Windows: run 08.1/3)
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from labkit import lesson

TICKET = (
    "Ticket #5121 from Priya (Finance): I got a new laptop yesterday and cannot sign in to the "
    "VPN. It says 'certificate not found'. I have a client call at 3pm."
)


class HelpdeskState(TypedDict, total=False):
    ticket: str
    category: str  # written by classify
    draft: str  # written by draft_reply
    final: str  # written by polish


@lesson("08.1/3", "Scenario: a three-step helpdesk workflow")
def main(ctx):
    llm = ChatOpenAI(
        model=ctx.model,
        base_url=ctx.settings.base_url,
        api_key=ctx.settings.api_key,
        temperature=0,
    )

    def ask(system: str, user: str) -> str:
        reply = llm.invoke([("system", system), ("human", user)])
        ctx.record_usage(reply.usage_metadata)
        return str(reply.content).strip()

    def classify(state: HelpdeskState) -> dict:
        label = ask(
            "Classify the IT ticket as exactly one word: hardware, network, access, software or other.",
            state["ticket"],
        )
        return {"category": label.lower()}

    def draft_reply(state: HelpdeskState) -> dict:
        text = ask(
            f"You are the Larkspur Labs IT helpdesk. The ticket is category '{state['category']}'. "
            "Draft a short, friendly reply with the next step.",
            state["ticket"],
        )
        return {"draft": text}

    def polish(state: HelpdeskState) -> dict:
        text = ask(
            "Rewrite this helpdesk reply: keep the facts, remove filler, at most three sentences, sign off 'Larkspur IT'.",
            state["draft"],
        )
        return {"final": text}

    ctx.step("Wire the workflow")
    builder = StateGraph(HelpdeskState)
    builder.add_node("classify", classify)
    builder.add_node("draft_reply", draft_reply)
    builder.add_node("polish", polish)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "draft_reply")
    builder.add_edge("draft_reply", "polish")
    builder.add_edge("polish", END)
    graph = builder.compile()
    ctx.note("Three nodes, three model calls, one shared state. Each node reads what earlier ones wrote.")

    ctx.step("Run it and watch the state flow")
    state: dict = {"ticket": TICKET}
    ctx.show_data("Input state", state)
    for update in graph.stream(state, stream_mode="updates"):
        for node, changes in update.items():
            state.update(changes)
            ctx.show_data(f"after '{node}' (fields written)", changes)

    ctx.step("The final state")
    ctx.show_data("Everything the workflow produced", state)
    ctx.note(f"Final reply:\n{state.get('final', '(none)')}")
    if not state.get("final"):
        ctx.note("The model returned an empty reply; the state above shows each step's output.")

    ctx.step("Where this goes next")
    ctx.note("The workflow is a straight line. A real helpdesk would act differently per category.")
    ctx.note("That needs a conditional edge (08.2): the graph picks the next node from the state.")


if __name__ == "__main__":
    main()
