"""03.3/3  A persistent helpdesk store with filters

The scenario: index the knowledge base into a ChromaDB store on disk (a temp directory), close
it, reopen it as a new process would, and answer tickets with team/audience filters. Search
results are mapped back to articles with ids, so an answer can cite KB-006.

Run it:   ./run 03.3/3          (Windows: run 03.3/3)
Needs the `rag` extra (chromadb + local embedding model). No chat model is used.
"""

import json
import tempfile
from pathlib import Path

import chromadb

from labkit import lesson

KB = json.loads(Path(__file__).with_name("kb.json").read_text(encoding="utf-8"))
TICKETS = [
    ("My laptop shuts off and the display is black", None),
    ("I need a new tool installed for my build pipeline", {"audience": {"$in": ["engineering", "all"]}}),
    ("Which security key do I need for the payments system", {"audience": "finance"}),
    ("Cannot reach the wiki from my kitchen table", {"team": "network"}),
]


@lesson("03.3/3", "A persistent helpdesk store with filters")
def main(ctx):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        ctx.step("Index the knowledge base into a store on disk")
        client = chromadb.PersistentClient(path=tmp)
        collection = client.get_or_create_collection("helpdesk-kb", configuration={"hnsw": {"space": "cosine"}})
        collection.upsert(  # upsert: running this twice does not duplicate rows
            ids=[a["id"] for a in KB],
            embeddings=ctx.embed([a["text"] for a in KB]),
            documents=[a["text"] for a in KB],
            metadatas=[{"team": a["team"], "audience": a["audience"]} for a in KB],
        )
        ctx.note(f"{collection.count()} articles stored in a temp directory")
        del collection, client

        ctx.step("Reopen the store (as a later process would) and search")
        client = chromadb.PersistentClient(path=tmp)
        collection = client.get_collection("helpdesk-kb")
        ctx.note(f"reopened, count = {collection.count()}")
        for ticket, where in TICKETS:
            res = collection.query(query_embeddings=ctx.embed([ticket]), n_results=2, where=where)
            ctx.note(f"Ticket: {ticket}   filter: {where}")
            for id_, doc, dist in zip(res["ids"][0], res["documents"][0], res["distances"][0]):
                ctx.note(f"  {id_} (distance {dist:.2f}) {doc[:75]}")

        ctx.step("What to take away")
        ctx.note("A persistent store survives restarts; the filter keeps engineers' and finance-only")
        ctx.note("articles out of everyone else's results. Distances are comparable only within one model.")
        del collection, client


if __name__ == "__main__":
    main()
