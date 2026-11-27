"""09.1/2  Generate, check, revise

The model drafts a helpdesk reply. A deterministic checker (plain Python) lists problems. If
there are any, the graph loops back to the model with the problems as feedback. At most 3
revisions, so the loop always ends.

Run it:   ./run 09.1/2          (Windows: run 09.1/2)
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from labkit import lesson

MAX_REVISIONS = 3
TICKET_ID = "LL-2041"
FORBIDDEN = ["guarantee", "as an ai", "i apologize for the inconvenience"]


class State(TypedDict):
    draft: str
    problems: list[str]
    revisions: int


def check_reply(text: str) -> list[str]:
    """Deterministic checks: length, mentions the ticket id, no forbidden phrases."""
    problems = []
    words = len(text.split())
    if words > 35:
        problems.append(f"too long: {words} words, limit is 35")
    if TICKET_ID not in text:
        problems.append(f"must mention the ticket id {TICKET_ID}")
    for phrase in FORBIDDEN:
        if phrase in text.lower():
            problems.append(f"contains forbidden phrase '{phrase}'")
    return problems


@lesson("09.1/2", "Generate, check, revise")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0.3)
    task = (
        f"Write a reply to an employee whose VPN token reset (ticket {TICKET_ID}) is done. "
        "Tell them to restart the VPN client."
    )

    def generate(state: State) -> dict:
        prompt = task
        if state["problems"]:
            prompt += "\n\nYour previous draft:\n" + state["draft"] + "\n\nFix these problems:\n- " + "\n- ".join(state["problems"])
        ai = model.invoke([("system", "You write short, friendly IT helpdesk replies for Larkspur Labs."), ("user", prompt)])
        ctx.record_usage(ai.usage_metadata)
        return {"draft": str(ai.content), "revisions": state["revisions"] + (1 if state["draft"] else 0)}

    def check(state: State) -> dict:
        problems = check_reply(state["draft"])
        ctx.note(f"[check] revision {state['revisions']}: {len(problems)} problem(s) {problems}")
        return {"problems": problems}

    def route(state: State) -> str:
        if not state["problems"]:
            ctx.note("[route] no problems: finish")
            return END
        if state["revisions"] >= MAX_REVISIONS:
            ctx.note(f"[route] cap of {MAX_REVISIONS} revisions reached with problems left: stop anyway")
            return END
        ctx.note("[route] problems found: back to generate with feedback")
        return "generate"

    ctx.step("Build the graph: generate -> check -> (generate | END)")
    g = StateGraph(State)
    g.add_node("generate", generate)
    g.add_node("check", check)
    g.add_edge(START, "generate")
    g.add_edge("generate", "check")
    g.add_conditional_edges("check", route, ["generate", END])
    graph = g.compile()
    ctx.note("Nodes: " + ", ".join(graph.get_graph().nodes))

    ctx.step("Run it")
    final = graph.invoke({"draft": "", "problems": [], "revisions": 0}, config={"recursion_limit": 12})

    ctx.step("Result")
    ctx.show_data("Final state", final)
    if final["problems"]:
        ctx.note("The reply still has problems after the cap. A real system would hand it to a person.")
    else:
        ctx.note("The reply passed every check.")


if __name__ == "__main__":
    main()
