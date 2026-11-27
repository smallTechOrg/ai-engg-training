"""03.5/1  Build the knowledge-base index

Combine everything from the module: short articles stay whole, the long handbook is chunked by heading with
overlap (03.2), every record gets team/audience metadata, and all of it goes into one Chroma collection (03.3).

Run it:   ./run 03.5/1          (Windows: run 03.5/1)
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


@lesson("03.5/1", "Build the knowledge-base index")
def main(ctx):
    ctx.step("Load and chunk")
    records = load_records()
    kb = [r for r in records if r["source"] == "kb"]
    hb = [r for r in records if r["source"] == "handbook"]
    ctx.note(f"{len(kb)} KB articles kept whole + {len(hb)} handbook chunks = {len(records)} records")
    ctx.show_data("One record of each kind", [kb[0], hb[0]])

    ctx.step("Embed and store")
    client, collection = build_collection(ctx, records)
    ctx.note(f"collection holds {collection.count()} records")

    ctx.step("Inspect the metadata the filters will use")
    for field in ("source", "team", "audience"):
        values = {}
        for m in collection.get()["metadatas"]:
            values[m[field]] = values.get(m[field], 0) + 1
        ctx.note(f"{field}: {values}")
    client.delete_collection(collection.name)


if __name__ == "__main__":
    main()
