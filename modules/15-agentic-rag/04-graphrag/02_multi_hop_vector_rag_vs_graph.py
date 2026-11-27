"""15.4/2  A multi-hop question: vector RAG against graph traversal

Question: "What is affected for staff when Atlas-2 is being patched?" No single document answers it. The
chain is Atlas-2 -> Directory Service -> Larkspur SSO -> Payroll Portal (and more), spread over five documents.

  * Vector RAG: top-3 paragraphs by similarity to the question (similarity finds "Atlas-2" text only).
  * Graph retrieval: find the question's entity in the graph, walk the edges BACKWARDS to everything that
    depends on it, directly or through other things, and hand those edges to the model as context.

Both answers are scored against a hand-written answer key (the services that really are affected),
by counting how many are mentioned. The graph is built by one model call, as in 15.4/1 (code copied).

Run it:   ./run 15.4/2          (Windows: run 15.4/2)
"""

import math
from pathlib import Path

import networkx as nx
from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson

DOCS_DIR = Path(__file__).parent / "docs"
RELATIONS = ["depends_on", "runs_on", "owned_by", "has_maintenance_window"]
QUESTION = "What is affected for staff when Atlas-2 is being patched on Sunday morning?"
# Written by hand from the documents, NOT taken from the extracted graph.
ANSWER_KEY = ["Directory Service", "Larkspur SSO", "VPN Gateway", "Payroll Portal", "Expense Tool", "Helpdesk Portal", "Badge Service"]

EXTRACT_PROMPT = """You extract a knowledge graph from IT documents.
Return triples [subject, relation, object]. Rules:
- relation must be one of: depends_on, runs_on, owned_by, has_maintenance_window.
- "A depends_on B" also covers "staff sign in to A through B". "X runs_on C" means X is hosted on C.
- Use the exact full names as they appear in the document titles (for example "Larkspur SSO", "Directory Service",
  "Payroll Portal", "Atlas-2", "Identity team"), never abbreviations or pronouns.
- For has_maintenance_window the object is the window text, for example "Sundays 02:00-04:00 UTC".
- Only facts stated in the text. Reply with JSON only: {"triples": [["subject", "relation", "object"], ...]}"""

ANSWER_PROMPT = """You are the IT helpdesk assistant at Larkspur Labs. Answer using ONLY the context below.
List every affected service by name, in at most four sentences. If the context is not enough, say what is missing."""


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    triples: list[list[str]]


def load_docs():
    docs = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        header, _, body = path.read_text(encoding="utf-8").partition("\n\n")
        meta = dict(line.split(": ", 1) for line in header.splitlines())
        docs.append({"id": meta["id"], "title": meta["title"], "text": body.strip()})
    return docs


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def score(answer):
    mentioned = [name for name in ANSWER_KEY if name.lower() in answer.lower()]
    return mentioned


@lesson("15.4/2", "Multi-hop: vector RAG against graph traversal")
def main(ctx):
    docs = load_docs()

    ctx.step("Build the graph (one model call)")
    corpus = "\n\n".join(f"### {d['title']}\n{d['text']}" for d in docs)
    response = ctx.client.chat.completions.create(
        model=ctx.model, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": EXTRACT_PROMPT}, {"role": "user", "content": corpus}])
    ctx.record_usage(response.usage, quiet=True)
    graph = nx.DiGraph()
    try:
        for s, r, o in Extraction.model_validate_json(response.choices[0].message.content or "").triples:
            if r in RELATIONS:
                graph.add_edge(s.strip(), o.strip(), relation=r)
    except (ValidationError, ValueError):
        ctx.note("Extraction was unusable; the graph stays empty and graph retrieval will find nothing.")
    ctx.note(f"{graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges.")

    ctx.step("Retrieval A: vector top-3 paragraphs")
    paragraphs = [(d["id"], p.strip()) for d in docs for p in d["text"].split("\n\n") if p.strip()]
    vectors = ctx.embed([p for _, p in paragraphs])
    qv = ctx.embed([QUESTION])[0]
    top = sorted(zip(vectors, paragraphs), key=lambda pair: cosine(qv, pair[0]), reverse=True)[:3]
    vector_context = "\n\n".join(f"[{doc}] {text}" for _, (doc, text) in top)
    ctx.note("retrieved: " + ", ".join(doc for _, (doc, _) in top))

    ctx.step("Retrieval B: walk the graph backwards from the entity in the question")
    entities = [n for n in graph.nodes if n.lower() in QUESTION.lower()]
    ctx.note(f"entities found in the question: {entities}")
    depends = nx.DiGraph((u, v, d) for u, v, d in graph.edges(data=True) if d["relation"] in ("depends_on", "runs_on"))
    affected = set()
    for entity in entities:
        if entity in depends:
            affected |= nx.ancestors(depends, entity)  # everything with a path TO the entity
    graph_lines = []
    for entity in entities:
        for service in sorted(affected | {entity}):
            for _, target, data in depends.out_edges(service, data=True):
                if target in affected | {entity}:
                    graph_lines.append(f"{service} {data['relation']} {target}")
        for _, window, data in graph.out_edges(entity, data=True):
            if data["relation"] == "has_maintenance_window":
                graph_lines.append(f"{entity} has_maintenance_window {window}")
    graph_context = "\n".join(graph_lines)
    ctx.note(f"{len(affected)} things depend on it, directly or indirectly: {sorted(affected)}")

    ctx.step("Answer with each context")
    results = {}
    for label, context in (("vector RAG", vector_context), ("graph retrieval", graph_context or "(nothing found)")):
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": ANSWER_PROMPT + "\n\nContext:\n" + context},
                      {"role": "user", "content": QUESTION}])
        ctx.note(f"--- {label} ---")
        ctx.show_response(response)
        results[label] = score(response.choices[0].message.content or "")

    ctx.step("Score against the answer key")
    for label, mentioned in results.items():
        ctx.note(f"{label:<16} names {len(mentioned)}/{len(ANSWER_KEY)} affected services: {mentioned}")
    ctx.note("Vector search matched the words 'Atlas-2' and 'patched'. The graph followed the edges. Note that")
    ctx.note("the graph's answer is only as complete as the extraction (15.4/1) and the relations you chose to follow.")


if __name__ == "__main__":
    main()
