"""15.2/1  Agentic RAG: retrieval as a tool the model chooses to call

In plain RAG the program always retrieves once, with the user's words. In agentic RAG retrieval is a
TOOL. The model decides whether to search, what to search for, and whether to search again. Here a
small tool loop (as in module 02) offers one tool, `search_kb`, and three questions show three
behaviours: no search at all, one search, and two searches with two different queries.

Run it:   ./run 15.2/1          (Windows: run 15.2/1)
"""

import json
import math
from pathlib import Path

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
TOP_K = 2
MAX_TURNS = 4  # hard cap on model calls per question

SYSTEM_PROMPT = """You are the IT helpdesk assistant at Larkspur Labs.
You have one tool, search_kb, that searches the IT knowledge base.
- Greetings, thanks and small talk need no search: just reply.
- For a policy or how-to question, search first and answer ONLY from what the tool returns.
- If the question has two separate parts, search once for each part with its own short query.
- If the tool returns nothing useful, say you do not know. Keep answers to two sentences."""

TOOLS = [{
    "type": "function",
    "function": {
        "name": "search_kb",
        "description": "Search the Larkspur Labs IT knowledge base. Returns the 2 most relevant passages.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "A short search query, key words rather than a sentence"}},
            "required": ["query"],
        },
    },
}]

QUESTIONS = [
    "Thanks, the reset link worked!",
    "How long does a VPN session last before I must sign in again?",
    "Which Wi-Fi network should a visitor join, and how many months between laptop replacements?",
]


def load_chunks():
    """One chunk per paragraph; superseded documents are left out (the fix from lesson 15.1)."""
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        header, _, body = path.read_text(encoding="utf-8").partition("\n\n")
        meta = dict(line.split(": ", 1) for line in header.splitlines())
        if meta["status"].startswith("superseded"):
            continue
        for position, paragraph in enumerate(p.strip() for p in body.split("\n\n") if p.strip()):
            chunks.append({"id": f"{meta['id']}#{position}", "text": paragraph})
    return chunks


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


@lesson("15.2/1", "The agent decides whether and what to retrieve")
def main(ctx):
    ctx.step("Index the knowledge base")
    chunks = load_chunks()
    vectors = ctx.embed([c["text"] for c in chunks])
    ctx.note(f"{len(chunks)} chunks indexed. Retrieval is now a function the model may call.")

    def search_kb(query):
        query_vector = ctx.embed([query])[0]
        ranked = sorted(zip(vectors, chunks), key=lambda pair: cosine(query_vector, pair[0]), reverse=True)
        return [{"id": c["id"], "text": c["text"]} for _, c in ranked[:TOP_K]]

    searches_per_question = []
    for question in QUESTIONS:
        ctx.step("Question: " + question)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}]
        searches = 0
        for turn in range(1, MAX_TURNS + 1):
            response = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=TOOLS)
            message = response.choices[0].message
            if not message.tool_calls:
                ctx.show_response(response)  # the final reply; this also records its tokens
                break
            ctx.record_usage(response.usage, quiet=True)  # a tool-call turn
            messages.append(message.model_dump(exclude_none=True))
            for call in message.tool_calls:
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                except ValueError:
                    arguments = {}
                result = search_kb(str(arguments.get("query", ""))) if call.function.name == "search_kb" else "unknown tool"
                searches += 1
                ctx.show_tool_call(call.function.name, arguments, [r["id"] + ": " + r["text"][:60] + "..." for r in result] if isinstance(result, list) else result)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
        else:
            ctx.note(f"Stopped: reached the cap of {MAX_TURNS} model calls without a final answer.")
        searches_per_question.append(searches)

    ctx.step("What to take away")
    ctx.note("Searches per question: " + ", ".join(str(n) for n in searches_per_question) + ".")
    ctx.note("Plain RAG would have searched exactly once for each, including for 'thanks', and would")
    ctx.note("have used one query for the two-part question. Here the model chose. The price is")
    ctx.note("extra model calls, and a model that sometimes decides badly. The model's choices are")
    ctx.note("not guaranteed to match this run: that is why script 3 puts checks around them.")


if __name__ == "__main__":
    main()
