"""13.1/3  Scenario: a knowledge-base article, reflected to a quality bar

The helpdesk keeps getting the same ticket: people are locked out after changing their password
on a phone. This script writes the knowledge-base article that should stop those tickets. A first
draft is rarely ready to publish, so the script critiques and revises it against a rubric until it
clears the bar or reaches the round cap.

Run it:   ./run 13.1/3          (Windows: run 13.1/3)
"""

import json
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from labkit import lesson

ISSUE = (
    "Recurring issue at Larkspur Labs: after changing their password, employees are locked out "
    "within minutes because their phone's mail app keeps retrying the OLD password. "
    "Fix: remove the account from the phone, wait 15 minutes for the lockout to clear (or ask IT to unlock), "
    "sign back in with the new password."
)
TASK = f"Write a short knowledge-base article (a title, then 4 to 6 numbered steps) for this issue.\n\n{ISSUE}"
RUBRIC = {
    "findable": "The title names the symptom the employee would search for.",
    "complete": "It covers the cause in one line and the full fix, including the wait and who to contact.",
    "followable": "Each step is one action, in order, with no jargon.",
    "concise": "No filler; fits on one screen.",
}
THRESHOLD = 5.0
MAX_ROUNDS = 3

CRITIC_SYSTEM = (
    "You are a harsh editor of an internal knowledge base. Score from 1 to 5 on each criterion; 5 is rare and a first draft usually earns 2 or 3. "
    "and give one sentence naming the most important fix. Reply with JSON only, shaped like this example: "
    '{"findable": 3, "complete": 3, "followable": 3, "concise": 3, "feedback": "one sentence"}\n'
    "Criteria:\n" + "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
)


class ArticleState(TypedDict, total=False):
    draft: str
    feedback: str
    scores: dict
    average: float
    rounds: int
    history: list[float]


@lesson("13.1/3", "Scenario: a knowledge-base article, reflected")
def main(ctx):
    llm = ChatOpenAI(
        model=ctx.model,
        base_url=ctx.settings.base_url,
        api_key=ctx.settings.api_key,
        temperature=0.3,
    )
    critic_llm = llm.bind(response_format={"type": "json_object"})

    def write(state: ArticleState) -> dict:
        reply = llm.invoke([("human", TASK)])
        ctx.record_usage(reply.usage_metadata, quiet=True)
        return {"draft": str(reply.content), "rounds": 0, "history": []}

    def review(state: ArticleState) -> dict:
        reply = critic_llm.invoke([("system", CRITIC_SYSTEM), ("human", state["draft"])])
        ctx.record_usage(reply.usage_metadata, quiet=True)
        try:
            data = json.loads(str(reply.content))
            scores = {k: int(data[k]) for k in RUBRIC}
            feedback = str(data.get("feedback", ""))
        except (ValueError, KeyError, TypeError):
            scores, feedback = {k: 0 for k in RUBRIC}, "Tighten the article against every criterion."
        average = sum(scores.values()) / len(scores)
        return {
            "scores": scores,
            "average": average,
            "feedback": feedback,
            "rounds": state["rounds"] + 1,
            "history": state["history"] + [average],
        }

    def revise(state: ArticleState) -> dict:
        reply = llm.invoke(
            [
                ("system", "Revise the knowledge-base article using the editor's feedback. Return only the article."),
                ("human", f"Issue:\n{ISSUE}\n\nArticle:\n{state['draft']}\n\nEditor feedback: {state['feedback']}"),
            ]
        )
        ctx.record_usage(reply.usage_metadata, quiet=True)
        return {"draft": str(reply.content)}

    def gate(state: ArticleState) -> str:
        if state["average"] >= THRESHOLD or state["rounds"] >= MAX_ROUNDS:
            return "publish"
        return "revise"

    builder = StateGraph(ArticleState)
    builder.add_node("write", write)
    builder.add_node("review", review)
    builder.add_node("revise", revise)
    builder.add_edge(START, "write")
    builder.add_edge("write", "review")
    builder.add_conditional_edges("review", gate, {"publish": END, "revise": "revise"})
    builder.add_edge("revise", "review")
    graph = builder.compile()

    ctx.step("The quality bar")
    ctx.show_data("Rubric (1-5 each)", RUBRIC)
    ctx.note(f"Publish when the average is >= {THRESHOLD}, or stop after {MAX_ROUNDS} reviews and flag it for a human.")

    ctx.step("Write, review, revise")
    state: dict = {}
    for update in graph.stream({}, stream_mode="updates"):
        for node, changes in update.items():
            state.update(changes)
            if node == "review":
                ctx.note(f"review #{changes['rounds']}: {changes['scores']} average {changes['average']:.2f}")
                ctx.note(f"   editor: {changes['feedback']}")
            else:
                ctx.note(f"{node}: new draft ({len(changes['draft'].split())} words)")

    ctx.step("Outcome")
    ctx.show_data("Average score per review", state["history"])
    if state["average"] >= THRESHOLD:
        ctx.note("Cleared the bar: ready to publish.")
    else:
        ctx.note("Did not clear the bar within the cap: send to a human editor with the feedback above.")
    ctx.note(f"Article:\n{state['draft']}")


if __name__ == "__main__":
    main()
