"""04.2/2  Saying "I don't know": a retrieval gate plus a prompt rule

Top-k retrieval never returns nothing, so "no answer" has to be decided somewhere. Two layers:
  1. a GATE in code: if the best chunk's score is below a threshold, refuse without calling the model;
  2. a PROMPT RULE: if chunks pass the gate but do not contain the answer, the model must say so.
We measure the best score for answerable and unanswerable questions, pick a threshold from the
gap, and count the model calls the gate saves.

Run it:   ./run 04.2/2          (Windows: run 04.2/2)
     or:  python modules/04-rag-by-hand/02-grounding-citations-and-saying-i-don-t-know/02_refusal_gate.py
Needs a chat model and the `rag` extra (local embedding model).
"""

from pathlib import Path

import numpy as np

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"
TOP_K = 2
REFUSAL = "I don't know based on the IT knowledge base."
# (question, is it answered by the KB?)
QUESTIONS = [
    ("How many wrong password attempts lock my account?", True),
    ("What do I do if the VPN will not connect?", True),
    ("Who approves software that costs 500 pounds a year?", True),
    ("What is the company's parental leave policy?", False),
    ("How do I claim travel expenses for a conference?", False),
    ("What is the canteen menu on Fridays?", False),
]
SYSTEM = (
    "You are the IT helpdesk assistant at Larkspur Labs. Answer ONLY from the context. "
    "Cite the source label in square brackets. "
    f'If the context does not contain the answer, reply exactly: "{REFUSAL}" and suggest the helpdesk.'
)


def load_chunks():
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        number = 0
        for paragraph in (p.strip() for p in path.read_text(encoding="utf-8").split("\n\n")):
            if not paragraph or paragraph.startswith("#") or paragraph.startswith("Updated:"):
                continue
            number += 1
            chunks.append({"source": f"{path.stem}#{number}", "text": paragraph})
    return chunks


def unit(m):
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


@lesson("04.2/2", "A refusal gate")
def main(ctx):
    ctx.step("1. Index the knowledge base and score every question")
    chunks = load_chunks()
    matrix = unit(np.array(ctx.embed([c["text"] for c in chunks])))
    qvecs = unit(np.array(ctx.embed([q for q, _ in QUESTIONS])))
    all_scores = qvecs @ matrix.T
    best = all_scores.max(axis=1)
    for (question, answerable), b in zip(QUESTIONS, best):
        ctx.note(f"best score {b:.2f}  {'in KB ' if answerable else 'NOT in KB'}  {question}")

    ctx.step("2. Pick a threshold from the gap")
    low_in = min(b for (_, a), b in zip(QUESTIONS, best) if a)
    high_out = max(b for (_, a), b in zip(QUESTIONS, best) if not a)
    ctx.note(f"Lowest answerable best-score: {low_in:.2f}. Highest unanswerable best-score: {high_out:.2f}.")
    if low_in > high_out:
        threshold = round((low_in + high_out) / 2, 2)
        ctx.note(f"The groups separate here. Threshold = midpoint = {threshold}.")
    else:
        threshold = round(low_in - 0.01, 2)
        ctx.note(f"The groups overlap. Threshold = just under the lowest answerable score = {threshold}.")
    ctx.note("Scores from one embedding model only compare relatively; recalibrate if you change models (04.3).")

    ctx.step("3. Answer all six: gate first, model second")
    calls = 0
    for (question, answerable), scores in zip(QUESTIONS, all_scores):
        top = [int(i) for i in np.argsort(-scores)[:TOP_K]]
        label = "in KB" if answerable else "NOT in KB"
        if scores[top[0]] < threshold:
            ctx.note(f"[{label}] GATE refused (score {scores[top[0]]:.2f} < {threshold}): {question}")
            ctx.note(f"   -> {REFUSAL} (no model call)")
            continue
        context = "\n\n".join(f"[{chunks[i]['source']}]\n{chunks[i]['text']}" for i in top)
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context:\n\n{context}\n\nQuestion: {question}"},
        ]
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        calls += 1
        ctx.note(f"[{label}] gate passed (score {scores[top[0]]:.2f}): {question}")
        reply = ctx.show_response(response) or ""
        if "don't know" in reply.lower() or "do not know" in reply.lower():
            ctx.note("   -> the PROMPT RULE refused (chunks passed the gate but lacked the answer)")

    ctx.step("4. A near miss: it passes the gate, so only the prompt rule can save us")
    near = "Can I install the Larkspur VPN client on my personal phone?"
    scores = (unit(np.array(ctx.embed([near]))) @ matrix.T)[0]
    top = [int(i) for i in np.argsort(-scores)[:TOP_K]]
    verdict = "passes" if scores[top[0]] >= threshold else "would be refused by"
    ctx.note(f"{near}  best score {scores[top[0]]:.2f}: {verdict} the gate. The KB never mentions phones.")
    context = "\n\n".join(f"[{chunks[i]['source']}]\n{chunks[i]['text']}" for i in top)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Context:\n\n{context}\n\nQuestion: {near}"},
    ]
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    calls += 1
    reply = ctx.show_response(response) or ""
    if "don't know" in reply.lower() or "do not know" in reply.lower():
        ctx.note("   -> the PROMPT RULE refused. Check the reply yourself: did it guess about phones?")
    else:
        ctx.note("   -> the model did NOT refuse. Read the reply: is the answer in the chunks, or inferred?")

    ctx.step("5. What the two layers bought")
    ctx.note(f"Model calls made: {calls} for {len(QUESTIONS) + 1} questions. The gate answers the clear misses for free.")
    ctx.note("The gate cannot judge meaning: a near-miss chunk can still pass, so the prompt rule stays.")
    ctx.note("Never tune the threshold on the same six questions you report results on: 04.3 uses a held-out set.")


if __name__ == "__main__":
    main()
