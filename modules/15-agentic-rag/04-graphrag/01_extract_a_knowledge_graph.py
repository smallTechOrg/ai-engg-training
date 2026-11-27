"""15.4/1  Build a knowledge graph: an LLM extracts entities and relations into networkx

GraphRAG starts by turning text into a graph: nodes are things (services, teams, clusters), edges are
relations ("Payroll Portal -depends_on-> Larkspur SSO"). Here one batched model call reads the seven short
documents in `docs/` and returns triples (subject, relation, object). We validate them against a closed list
of relations, build a `networkx.DiGraph`, and look at it.

Run it:   ./run 15.4/1          (Windows: run 15.4/1)
"""

from pathlib import Path

import networkx as nx
from pydantic import BaseModel, ConfigDict, ValidationError

from labkit import lesson

DOCS_DIR = Path(__file__).parent / "docs"
RELATIONS = ["depends_on", "runs_on", "owned_by", "has_maintenance_window"]

EXTRACT_PROMPT = """You extract a knowledge graph from IT documents.
Return triples [subject, relation, object]. Rules:
- relation must be one of: depends_on, runs_on, owned_by, has_maintenance_window.
- "A depends_on B" also covers "staff sign in to A through B". "X runs_on C" means X is hosted on C.
- Use the exact full names as they appear in the document titles (for example "Larkspur SSO", "Directory Service",
  "Payroll Portal", "Atlas-2", "Identity team"), never abbreviations or pronouns.
- For has_maintenance_window the object is the window text, for example "Sundays 02:00-04:00 UTC".
- Only facts stated in the text. Reply with JSON only: {"triples": [["subject", "relation", "object"], ...]}"""


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


def build_graph(triples):
    """Keep only well-formed triples with a known relation. Returns (graph, rejected)."""
    graph, rejected = nx.DiGraph(), []
    for triple in triples:
        if len(triple) != 3 or triple[1] not in RELATIONS or not triple[0].strip() or not triple[2].strip():
            rejected.append(triple)
            continue
        subject, relation, obj = (t.strip() for t in triple)
        graph.add_edge(subject, obj, relation=relation)
    return graph, rejected


@lesson("15.4/1", "Extract a knowledge graph with an LLM")
def main(ctx):
    ctx.step("The documents")
    docs = load_docs()
    for d in docs:
        ctx.note(f"{d['id']:<18} {d['text'][:70]}...")

    ctx.step("One batched call extracts triples from every document")
    corpus = "\n\n".join(f"### {d['title']}\n{d['text']}" for d in docs)
    response = ctx.client.chat.completions.create(
        model=ctx.model, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": EXTRACT_PROMPT}, {"role": "user", "content": corpus}])
    ctx.show_response(response)

    ctx.step("Validate and build the graph")
    try:
        triples = Extraction.model_validate_json(response.choices[0].message.content or "").triples
    except (ValidationError, ValueError):
        triples = []
        ctx.note("The model did not return usable JSON, so the graph is empty. Run again, or check your endpoint's JSON mode.")
    graph, rejected = build_graph(triples)
    ctx.note(f"{len(triples)} triples returned, {graph.number_of_edges()} kept, {len(rejected)} rejected: {rejected[:3]}")
    ctx.note(f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges.")
    for subject, obj, data in sorted(graph.edges(data=True)):
        ctx.note(f"  {subject}  --{data['relation']}-->  {obj}")

    ctx.step("Check it against what we know is in the documents")
    expected = [("Larkspur SSO", "Directory Service"), ("Directory Service", "Atlas-2"), ("Payroll Portal", "Larkspur SSO")]
    for a, b in expected:
        ctx.note(f"  edge {a} -> {b}: {'found' if graph.has_edge(a, b) else 'MISSING (name mismatch or not extracted)'}")
    ctx.note("Extraction is the weak link of GraphRAG: a missed edge or two spellings of one entity")
    ctx.note("silently break paths later. Always inspect the graph, and ideally score it against a hand-made one.")


if __name__ == "__main__":
    main()
