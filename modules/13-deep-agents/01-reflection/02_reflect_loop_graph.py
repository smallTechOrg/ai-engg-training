"""13.1/2  Reflection as a LangGraph loop

The same three roles as a graph: draft -> critique -> (good enough? finish : revise -> critique).
A conditional edge decides after every critique. Two stop rules, both required:

  - quality: the average score reaches THRESHOLD;
  - budget:  MAX_ROUNDS critiques have happened (a loop that calls a model must have a hard cap).

Run it:   ./run 13.1/2          (Windows: run 13.1/2)
"""

import json
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from labkit import lesson

TASK = "Write a 3-sentence reply to an employee whose laptop battery drains in under an hour."
RUBRIC = {
    "clarity": "A non-technical reader understands every sentence.",
    "actionability": "It gives at least one concrete step the employee can take now.",
    "tone": "Friendly and professional, no blame, no jargon.",
}
THRESHOLD = 4.8
MAX_ROUNDS = 3

CRITIC_SYSTEM = (
    "You are a harsh reviewer. Score from 1 (poor) to 5 (excellent) on each criterion; 5 is rare and a first draft usually earns 2 or 3. "
    "and give one sentence of feedback. Reply with JSON only, shaped like this example: "
    '{"clarity": 3, "actionability": 3, "tone": 3, "feedback": "one sentence"}\n'
    "Criteria:\n" + "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
)


class ReflectState(TypedDict, total=False):
    draft: str
    feedback: str
    average: float
    rounds: int  # critiques done so far
    history: list[float]  # average score after each critique


@lesson("13.1/2", "Reflection as a LangGraph loop")
def main(ctx):
    llm = ChatOpenAI(
        model=ctx.model,
        base_url=ctx.settings.base_url,
        api_key=ctx.settings.api_key,
        temperature=0.3,
    )
    critic_llm = llm.bind(response_format={"type": "json_object"})

    def generate(state: ReflectState) -> dict:
        reply = llm.invoke([("human", TASK)])
        ctx.record_usage(reply.usage_metadata, quiet=True)
        return {"draft": str(reply.content), "rounds": 0, "history": []}

    def critique(state: ReflectState) -> dict:
        reply = critic_llm.invoke([("system", CRITIC_SYSTEM), ("human", state["draft"])])
        ctx.record_usage(reply.usage_metadata, quiet=True)
        try:
            data = json.loads(str(reply.content))
            scores = [int(data[k]) for k in RUBRIC]
            average, feedback = sum(scores) / len(scores), str(data.get("feedback", ""))
        except (ValueError, KeyError, TypeError):
            # Unusable critique: score 0 and ask for a general improvement. The loop's cap still applies.
            average, feedback = 0.0, "Make it clearer, more actionable and friendlier."
        return {
            "average": average,
            "feedback": feedback,
            "rounds": state["rounds"] + 1,
            "history": state["history"] + [average],
        }

    def revise(state: ReflectState) -> dict:
        reply = llm.invoke(
            [
                ("system", "Improve the text. Keep it to 3 sentences. Return only the improved text."),
                ("human", f"Task: {TASK}\n\nDraft:\n{state['draft']}\n\nReviewer feedback: {state['feedback']}"),
            ]
        )
        ctx.record_usage(reply.usage_metadata, quiet=True)
        return {"draft": str(reply.content)}

    def should_continue(state: ReflectState) -> str:
        if state["average"] >= THRESHOLD:
            return "done"
        if state["rounds"] >= MAX_ROUNDS:
            return "done"
        return "revise"

    ctx.step("Build the loop")
    builder = StateGraph(ReflectState)
    builder.add_node("generate", generate)
    builder.add_node("critique", critique)
    builder.add_node("revise", revise)
    builder.add_edge(START, "generate")
    builder.add_edge("generate", "critique")
    builder.add_conditional_edges("critique", should_continue, {"done": END, "revise": "revise"})
    builder.add_edge("revise", "critique")
    graph = builder.compile()
    ctx.note(f"Stops when the average score >= {THRESHOLD} or after {MAX_ROUNDS} critiques, whichever comes first.")
    ctx.console.print(graph.get_graph().draw_mermaid(), markup=False, highlight=False)

    ctx.step("Run it")
    state: dict = {}
    for update in graph.stream({}, stream_mode="updates"):
        for node, changes in update.items():
            state.update(changes)
            if node == "critique":
                ctx.note(f"critique #{changes['rounds']}: average {changes['average']:.2f} - {changes['feedback']}")
            else:
                ctx.note(f"{node}: wrote a new draft ({len(changes['draft'].split())} words)")

    ctx.step("Result")
    ctx.show_data("Average score after each critique", state["history"])
    if state["average"] >= THRESHOLD:
        ctx.note(f"Stopped on quality after {state['rounds']} critique(s).")
    else:
        ctx.note(f"Hit the cap of {MAX_ROUNDS} critiques without reaching {THRESHOLD}; returning the latest draft.")
    ctx.note(f"Final text:\n{state['draft']}")


if __name__ == "__main__":
    main()
