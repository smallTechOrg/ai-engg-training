"""15.4/3  Scenario: a helpdesk assistant that routes between graph and vector retrieval

A graph is not better than a vector index, it is good at different questions. This script keeps both and
lets the model pick per question:

  - "relationship" questions (who owns X, what depends on X, what breaks if Y fails) -> graph neighbourhood;
  - "lookup" questions (a fact that sits inside one paragraph)                        -> vector top-2.

Graph retrieval: link the entities named in the question, take every edge within 2 hops (treating edges as
undirected so we see both what a service needs and what needs it), and give those edges as context. Each answer is
checked for a keyword from a hand-written answer key.

Run it:   ./run 15.4/3          (Windows: run 15.4/3)
"""

import math
from pathlib import Path

import networkx as nx
from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson

DOCS_DIR = Path(__file__).parent / "docs"
RELATIONS = ["depends_on", "runs_on", "owned_by", "has_maintenance_window"]
RADIUS = 2

# (question, keyword the correct answer must contain)
TEST_SET = [
    ("Which team owns the sign-in system that the Payroll Portal relies on?", "identity"),
    ("On what day of the month are payslips published?", "25"),
    ("If the Directory Service goes read-only, which finance tools stop working?", "expense"),
]

EXTRACT_PROMPT = """You extract a knowledge graph from IT documents.
Return triples [subject, relation, object]. Rules:
- relation must be one of: depends_on, runs_on, owned_by, has_maintenance_window.
- "A depends_on B" also covers "staff sign in to A through B". "X runs_on C" means X is hosted on C.
- Use the exact full names as they appear in the document titles (for example "Larkspur SSO", "Directory Service",
  "Payroll Portal", "Atlas-2", "Identity team"), never abbreviations or pronouns.
- For has_maintenance_window the object is the window text, for example "Sundays 02:00-04:00 UTC".
- Only facts stated in the text. Reply with JSON only: {"triples": [["subject", "relation", "object"], ...]}"""

ROUTER_PROMPT = """Choose how to retrieve for a helpdesk question.
"graph": the answer depends on relationships between systems or teams (ownership, dependencies, what is affected).
"vector": the answer is a single fact written in one paragraph (a date, a number, a procedure step).
Reply with JSON only: {"mode": "graph"} or {"mode": "vector"}"""

ANSWER_PROMPT = """You are the IT helpdesk assistant at Larkspur Labs. Answer using ONLY the context below, in at most
two sentences. If the context is not enough, say so."""


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    triples: list[list[str]]


class Route(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str


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


@lesson("15.4/3", "Route between graph and vector retrieval")
def main(ctx):
    docs = load_docs()

    ctx.step("Build both indexes")
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
        ctx.note("Extraction was unusable; graph questions will have no context.")
    paragraphs = [(d["id"], p.strip()) for d in docs for p in d["text"].split("\n\n") if p.strip()]
    vectors = ctx.embed([p for _, p in paragraphs])
    ctx.note(f"graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges. vector index: {len(paragraphs)} paragraphs.")

    def graph_context(question):
        undirected = graph.to_undirected(as_view=False)
        entities = [n for n in graph.nodes if n.lower() in question.lower()]
        keep = set()
        for entity in entities:
            keep |= set(nx.single_source_shortest_path_length(undirected, entity, cutoff=RADIUS))
        lines = [f"{u} {d['relation']} {v}" for u, v, d in graph.edges(data=True) if u in keep and v in keep]
        return entities, "\n".join(lines)

    def vector_context(question):
        qv = ctx.embed([question])[0]
        top = sorted(zip(vectors, paragraphs), key=lambda pair: cosine(qv, pair[0]), reverse=True)[:2]
        return [doc for _, (doc, _) in top], "\n\n".join(f"[{doc}] {text}" for _, (doc, text) in top)

    passed = 0
    for question, keyword in TEST_SET:
        ctx.step("Question: " + question)
        reply = ctx.client.chat.completions.create(
            model=ctx.model, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": question}])
        ctx.record_usage(reply.usage, quiet=True)
        try:
            mode = Route.model_validate_json(reply.choices[0].message.content or "").mode
        except (ValidationError, ValueError):
            mode = "vector"
        if mode not in ("graph", "vector"):
            mode = "vector"  # an unknown route falls back to the safe default
        if mode == "graph":
            entities, context = graph_context(question)
            ctx.note(f"route: graph. entities: {entities}. {len(context.splitlines())} edges within {RADIUS} hops.")
            if not context:
                ctx.note("no entity matched, falling back to vector retrieval")
                mode = "vector"
        if mode == "vector":
            ids, context = vector_context(question)
            ctx.note(f"route: vector. retrieved: {ids}")
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[{"role": "system", "content": ANSWER_PROMPT + "\n\nContext:\n" + context},
                      {"role": "user", "content": question}])
        ctx.show_response(response)
        ok = keyword in (response.choices[0].message.content or "").lower()
        passed += ok
        ctx.note(f"answer contains {keyword!r}: {ok}")

    ctx.step("Result")
    ctx.note(f"{passed}/{len(TEST_SET)} answers contain the expected keyword.")
    ctx.note("Graph retrieval costs an extraction pass up front and goes stale when the documents change: rebuild")
    ctx.note("the graph (or just the changed documents) on every content update, or you serve outdated edges.")


if __name__ == "__main__":
    main()
