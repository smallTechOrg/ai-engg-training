"""03.5/2  Search with filters and hybrid ranking

One search() function with three modes (vector, BM25, hybrid RRF) and a Chroma metadata filter, then a few
helpdesk questions run through it.

Run it:   ./run 03.5/2          (Windows: run 03.5/2)
Needs the `rag` extra (chromadb, rank_bm25, local embedding model). No chat model is used.
"""

import json
import re
import uuid
from pathlib import Path

import chromadb
import numpy as np
from rank_bm25 import BM25Okapi

from labkit import lesson

KB = json.loads(Path(__file__).with_name("kb.json").read_text(encoding="utf-8"))
HANDBOOK = Path(__file__).with_name("handbook.md")
SECTION_TEAM = {"Passwords and accounts": "access", "Network and VPN": "network", "Laptops and devices": "hardware",
                "Software and access requests": "software", "Security basics": "security"}
STOP = {"a", "an", "the", "my", "i", "me", "to", "of", "on", "in", "at", "is", "it", "and", "or", "do", "does",
        "not", "no", "for", "with", "from", "if", "so", "be", "are", "was", "after", "when", "how", "what", "will", "can"}


def tokens(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def chunk_section(body, max_chars=350):
    """Whole sentences up to max_chars; the next chunk repeats the last sentence (overlap)."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", body.replace("\n\n", " ")) if s]
    chunks, current = [], []
    for sentence in sentences:
        if current and len(" ".join(current + [sentence])) > max_chars:
            chunks.append(" ".join(current))
            current = current[-1:]
        current.append(sentence)
    if current:
        chunks.append(" ".join(current))
    return chunks


def load_records():
    """Short KB articles stay whole; the long handbook is chunked by heading. Same metadata for both."""
    records = [{"id": a["id"], "text": a["text"], "source": "kb", "team": a["team"], "audience": a["audience"]} for a in KB]
    parts = re.split(r"^## (.+)$", HANDBOOK.read_text(encoding="utf-8"), flags=re.MULTILINE)
    for i in range(1, len(parts), 2):
        heading, body = parts[i].strip(), parts[i + 1].strip()
        for n, chunk in enumerate(chunk_section(body), 1):
            records.append({"id": f"HB-{i // 2 + 1}.{n}", "text": chunk, "source": "handbook",
                            "team": SECTION_TEAM[heading], "audience": "all", "heading": heading})
    return records


def build_collection(ctx, records):
    client = chromadb.EphemeralClient()
    collection = client.create_collection(f"capstone-{uuid.uuid4().hex[:8]}", configuration={"hnsw": {"space": "cosine"}})
    collection.add(
        ids=[r["id"] for r in records],
        embeddings=ctx.embed([r["text"] for r in records]),
        documents=[r["text"] for r in records],
        metadatas=[{k: r[k] for k in ("source", "team", "audience")} for r in records],
    )
    return client, collection


def search(ctx, collection, records, query, k=3, where=None, mode="hybrid"):
    """Return the ids of the top k records. mode: vector | bm25 | hybrid (RRF, BM25 matches only)."""
    allowed = collection.get(where=where)["ids"] if where else [r["id"] for r in records]
    by_id = {r["id"]: r for r in records}
    n = min(len(allowed), 50)
    vector_ids = collection.query(query_embeddings=ctx.embed([query]), n_results=n, where=where)["ids"][0]
    docs = [by_id[i] for i in allowed]
    scores = BM25Okapi([tokens(d["text"]) for d in docs]).get_scores(tokens(query))
    bm25_ids = [docs[i]["id"] for i in np.argsort(-scores) if scores[i] > 0]
    if mode == "vector":
        return vector_ids[:k]
    if mode == "bm25":
        return bm25_ids[:k]
    fused = {}
    for ranking in (vector_ids, bm25_ids):
        for rank, id_ in enumerate(ranking, 1):
            fused[id_] = fused.get(id_, 0.0) + 1.0 / (60 + rank)
    return [i for i, _ in sorted(fused.items(), key=lambda kv: -kv[1])][:k]

QUESTIONS = [
    ("somebody took my handset on the train", None),
    ("the wiki will not load but the VPN says connected", None),
    ("how do I get a hardware security key", {"audience": "finance"}),
    ("laptop will not update", {"team": "software"}),
    ("laptop will not update", {"$and": [{"team": "software"}, {"source": "kb"}]}),
]


@lesson("03.5/2", "Search with filters and hybrid ranking")
def main(ctx):
    records = load_records()
    by_id = {r["id"]: r for r in records}
    client, collection = build_collection(ctx, records)
    for question, where in QUESTIONS:
        ctx.step(f"{question}   filter: {where}")
        for mode in ("vector", "hybrid"):
            for rank, id_ in enumerate(search(ctx, collection, records, question, k=2, where=where, mode=mode), 1):
                r = by_id[id_]
                ctx.note(f"{mode:<6} #{rank} {id_:<7} [{r['source']}/{r['team']}] {r['text'][:70]}")
    client.delete_collection(collection.name)


if __name__ == "__main__":
    main()
