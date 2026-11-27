"""04.3/3  Measuring answers: key-fact checks and an LLM judge for faithfulness

Retrieval metrics say the answer was available. Answer metrics ask: did the model use it?
Three checks per answer:
  correct   - the expected key fact appears (cheap string check, from eval_set.json)
  refused   - for questions not in the KB, the answer says "I don't know" (and for the others it does not)
  faithful  - an LLM judge reads context + answer and says whether every claim is supported
The judge call is batched (one call for all answers). We also plant one deliberately unfaithful
answer to see whether the judge catches it. Judges are fallible; that test is how you find out.

Run it:   ./run 04.3/3          (Windows: run 04.3/3)
     or:  python modules/04-rag-by-hand/03-measuring-retrieval-and-answer-quality/03_judge_answers.py
Needs a chat model and the `rag` extra (local embedding model).
"""

import json
from pathlib import Path

import numpy as np

from labkit import lesson

HERE = Path(__file__).parent
KB_DIR = HERE / "kb"
TOP_K = 3
PICK = ["q1", "q3", "q8", "q10", "q13", "q14"]  # four answerable, two not in the KB
SYSTEM = (
    "You are the IT helpdesk assistant at Larkspur Labs. Answer ONLY from the context, briefly. "
    "Cite source labels in square brackets. If the context lacks the answer, reply exactly: "
    "\"I don't know based on the IT knowledge base.\""
)
JUDGE = (
    "You are a strict fact-checker. For each item you get a CONTEXT and an ANSWER. "
    "An answer is faithful only if EVERY factual claim in it is supported by the context. "
    "Saying 'I don't know' is faithful. Reply as JSON: "
    '{"verdicts": [{"id": "<id>", "faithful": true or false, "reason": "<one short sentence>"}]}'
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


def declined(answer):
    return "don't know" in answer.lower() or "do not know" in answer.lower()


@lesson("04.3/3", "Judging answers")
def main(ctx):
    ctx.step("1. Retrieve and answer six labelled questions")
    chunks = load_chunks()
    items = {q["id"]: q for q in json.loads((HERE / "eval_set.json").read_text(encoding="utf-8"))}
    picked = [items[i] for i in PICK]
    matrix = unit(np.array(ctx.embed([c["text"] for c in chunks])))
    qvecs = unit(np.array(ctx.embed([q["question"] for q in picked])))
    rows = []
    for q, qvec in zip(picked, qvecs):
        top = [int(i) for i in np.argsort(-(matrix @ qvec))[:TOP_K]]
        context = "\n\n".join(f"[{chunks[i]['source']}]\n{chunks[i]['text']}" for i in top)
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context:\n\n{context}\n\nQuestion: {q['question']}"},
        ]
        response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        answer = ctx.show_response(response) or ""
        rows.append({"q": q, "context": context, "answer": answer, "retrieved": [chunks[i]["source"] for i in top]})

    ctx.step("2. Cheap deterministic checks")
    for r in rows:
        q = r["q"]
        if q["gold"]:
            r["hit"] = any(g in r["retrieved"] for g in q["gold"])
            r["correct"] = all(k in r["answer"].lower() for k in q["must_contain"])
            r["refused_ok"] = not declined(r["answer"])
        else:
            r["hit"], r["correct"] = None, None
            r["refused_ok"] = declined(r["answer"])
        ctx.note(f"{q['id']:<4} retrieval_hit={r['hit']} key_fact={r['correct']} refusal_behaviour_ok={r['refused_ok']}")

    ctx.step("3. One batched LLM-judge call for faithfulness, with one planted bad answer")
    planted = {
        "q1": "Larkspur Labs replaces laptops every 5 years, and you also get a free monitor with each new laptop.",
    }
    ctx.note(f"Planted item 'q1-planted' (should be judged NOT faithful): {planted['q1']}")
    batch = [{"id": r["q"]["id"], "context": r["context"], "answer": r["answer"]} for r in rows]
    laptop_context = next(r["context"] for r in rows if r["q"]["id"] == "q1")
    batch.append({"id": "q1-planted", "context": laptop_context, "answer": planted["q1"]})
    messages = [
        {"role": "system", "content": JUDGE},
        {"role": "user", "content": json.dumps(batch, ensure_ascii=False)},
    ]
    response = ctx.client.chat.completions.create(
        model=ctx.model, messages=messages, temperature=0, response_format={"type": "json_object"}
    )
    raw = ctx.show_response(response) or ""
    try:
        verdicts = {v["id"]: v for v in json.loads(raw)["verdicts"]}
    except (ValueError, KeyError, TypeError):
        verdicts = {}
        ctx.note("The judge did not return the expected JSON. No faithfulness scores this run (an explained outcome).")

    ctx.step("4. The report")
    ctx.note(f"{'id':<11} {'hit':<6} {'key fact':<9} {'refusal ok':<11} {'faithful (judge)'}")
    for r in rows + [{"q": {"id": "q1-planted"}, "hit": None, "correct": None, "refused_ok": None}]:
        qid = r["q"]["id"]
        v = verdicts.get(qid, {})
        ctx.note(f"{qid:<11} {str(r['hit']):<6} {str(r['correct']):<9} {str(r['refused_ok']):<11} {v.get('faithful', 'n/a')}")
    if "q1-planted" in verdicts:
        caught = verdicts["q1-planted"].get("faithful") is False
        ctx.note("The judge " + ("CAUGHT" if caught else "MISSED") + " the planted unfaithful answer.")
    faithful = [v.get("faithful") for k, v in verdicts.items() if k != "q1-planted"]
    if faithful:
        ctx.note(f"Faithfulness on real answers: {sum(f is True for f in faithful)}/{len(faithful)}")

    ctx.step("What to take away")
    ctx.note("Retrieval hit, key fact, refusal behaviour and faithfulness are four different failures; report all four.")
    ctx.note("A judge is a model: test it with planted answers, keep its prompt fixed, and spot-check a sample by hand.")
    ctx.note("Faithful is not the same as correct: an answer can be fully supported by the wrong chunk.")


if __name__ == "__main__":
    main()
