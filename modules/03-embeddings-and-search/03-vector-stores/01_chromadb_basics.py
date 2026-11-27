"""03.3/1  ChromaDB: collections, metadata filters, CRUD

A vector store keeps vectors next to their text and metadata and answers "nearest k" queries
without you writing the cosine loop from 03.1. This script uses ChromaDB in memory with the
vectors from ctx.embed, so Chroma never downloads its own embedding model.

Run it:   ./run 03.3/1          (Windows: run 03.3/1)
Needs the `rag` extra (chromadb + local embedding model). No chat model is used.
"""

import json
import uuid
from pathlib import Path

import chromadb

from labkit import lesson

KB = json.loads(Path(__file__).with_name("kb.json").read_text(encoding="utf-8"))


def show_hits(ctx, result):
    for id_, doc, meta, dist in zip(result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]):
        ctx.note(f"  {id_} [{meta['team']}/{meta['audience']}] distance {dist:.3f}: {doc[:80]}")


@lesson("03.3/1", "ChromaDB: collections, filters, CRUD")
def main(ctx):
    ctx.step("Create an in-memory client and a collection")
    client = chromadb.EphemeralClient()
    # Unique name: the ephemeral client shares one in-process store, so reruns must not collide.
    collection = client.create_collection(f"helpdesk-{uuid.uuid4().hex[:8]}", configuration={"hnsw": {"space": "cosine"}})
    ctx.note(f"collection {collection.name!r}, distance = cosine (distance = 1 - similarity, lower is closer)")

    ctx.step("Add the knowledge base: ids, vectors, documents, metadata")
    vectors = ctx.embed([a["text"] for a in KB])
    collection.add(
        ids=[a["id"] for a in KB],
        embeddings=vectors,
        documents=[a["text"] for a in KB],
        metadatas=[{"team": a["team"], "audience": a["audience"]} for a in KB],
    )
    ctx.note(f"count = {collection.count()}")

    query = "I replaced my phone and my login codes no longer work"
    q = ctx.embed([query])

    ctx.step("Query: nearest 3")
    ctx.note(query)
    show_hits(ctx, collection.query(query_embeddings=q, n_results=3))

    ctx.step("Query with a metadata filter: only team = network")
    show_hits(ctx, collection.query(query_embeddings=q, n_results=3, where={"team": "network"}))
    ctx.note("The filter is applied inside the store, so you still get 3 results from the allowed set.")

    ctx.step("A combined filter: engineering OR all audience, AND team = software")
    where = {"$and": [{"team": "software"}, {"audience": {"$in": ["engineering", "all"]}}]}
    show_hits(ctx, collection.query(query_embeddings=q, n_results=3, where=where))

    ctx.step("get(): fetch by id or by filter, no vector involved")
    got = collection.get(where={"audience": "finance"})
    ctx.note(f"finance articles: {got['ids']}")

    ctx.step("Update, upsert, delete")
    collection.update(ids=["KB-011"], metadatas=[{"team": "security", "audience": "all"}])
    ctx.note(f"KB-011 team is now {collection.get(ids=['KB-011'])['metadatas'][0]['team']!r} (the vector is unchanged)")
    new_text = "Report a lost phone or laptop to IT at once; it is locked and wiped remotely and a replacement is issued after approval."
    collection.upsert(ids=["KB-011"], embeddings=ctx.embed([new_text]), documents=[new_text], metadatas=[{"team": "hardware", "audience": "all"}])
    collection.delete(ids=["KB-024"])
    ctx.note(f"after upsert + delete: count = {collection.count()}")

    ctx.step("What to take away")
    ctx.note("add / query / get / update / upsert / delete cover the whole lifecycle. If you change a")
    ctx.note("document's text you must also change its vector; metadata alone can change cheaply.")
    client.delete_collection(collection.name)


if __name__ == "__main__":
    main()
