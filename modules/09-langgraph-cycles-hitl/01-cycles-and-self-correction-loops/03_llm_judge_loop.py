"""09.1/3  The checker is an LLM judge

Same loop as script 2, but the checker is a second model call that returns structured
{ok, problems}. A judge can assess things code cannot (tone, whether the reply answers the
question) but it is another model call: it costs tokens and can be wrong. The loop is capped.

Run it:   ./run 09.1/3          (Windows: run 09.1/3)
"""

from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from labkit import lesson

MAX_REVISIONS = 2  # each round is two model calls, so this keeps the script under 8 calls


class Verdict(BaseModel):
    ok: bool = Field(description="True only if the reply is polite, tells the employee what to do next, and is under 60 words.")
    problems: list[str] = Field(description="Concrete problems to fix. Empty if ok.")


class State(TypedDict):
    draft: str
    problems: list[str]
    revisions: int
    ok: bool


@lesson("09.1/3", "LLM judge in the loop")
def main(ctx):
    kw = dict(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key)
    writer = ChatOpenAI(temperature=0.3, **kw)
    judge = ChatOpenAI(temperature=0, **kw).with_structured_output(Verdict, include_raw=True)

    request = (
        "Larkspur Labs employee message: 'My laptop fan is very loud since Monday and it gets hot. "
        "Ticket LL-2043.' Write the helpdesk reply."
    )

    def generate(state: State) -> dict:
        prompt = request
        if state["problems"]:
            prompt += "\n\nPrevious draft:\n" + state["draft"] + "\n\nFix:\n- " + "\n- ".join(state["problems"])
        ai = writer.invoke([("system", "You write short, polite IT helpdesk replies."), ("user", prompt)])
        ctx.record_usage(ai.usage_metadata)
        return {"draft": str(ai.content), "revisions": state["revisions"] + (1 if state["draft"] else 0)}

    def check(state: State) -> dict:
        out = judge.invoke([
            ("system", "You are a strict reviewer of helpdesk replies. Return ok and a list of problems."),
            ("user", f"Employee message:\n{request}\n\nReply to review:\n{state['draft']}"),
        ])
        ctx.record_usage(getattr(out["raw"], "usage_metadata", None))
        verdict = out["parsed"]
        if verdict is None:
            ctx.note(f"[judge] could not parse a verdict ({out.get('parsing_error')}); treating as not ok")
            return {"ok": False, "problems": ["judge returned no usable verdict"]}
        ctx.note(f"[judge] ok={verdict.ok} problems={verdict.problems}")
        return {"ok": verdict.ok, "problems": verdict.problems}

    def route(state: State) -> str:
        if state["ok"]:
            ctx.note("[route] judge approved: finish")
            return END
        if state["revisions"] >= MAX_REVISIONS:
            ctx.note(f"[route] cap of {MAX_REVISIONS} revisions reached: stop with the last draft")
            return END
        ctx.note("[route] judge rejected: revise")
        return "generate"

    ctx.step("Build and run generate -> judge -> (generate | END)")
    g = StateGraph(State)
    g.add_node("generate", generate)
    g.add_node("check", check)
    g.add_edge(START, "generate")
    g.add_edge("generate", "check")
    g.add_conditional_edges("check", route, ["generate", END])
    graph = g.compile()
    final = graph.invoke({"draft": "", "problems": [], "revisions": 0, "ok": False}, config={"recursion_limit": 10})

    ctx.step("Result")
    ctx.show_data("Final state", final)
    ctx.note("A judge can be too strict or too lenient. The cap guarantees the loop ends either way.")


if __name__ == "__main__":
    main()
