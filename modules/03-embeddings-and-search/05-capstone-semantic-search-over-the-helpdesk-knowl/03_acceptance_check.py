"""03.5/3  Acceptance check

Twelve labelled questions, three modes, and the capstone's acceptance criteria turned into code. The script
prints a pass/fail line per criterion; failing one is an outcome to read, not a crash.

Run it:   ./run 03.5/3          (Windows: run 03.5/3)
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

# (question, acceptable record ids, optional filter)
CASES = [
    ("somebody took my handset on the train", {"KB-011"}, None),
    ("can't log in after too many wrong passwords", {"KB-002", "HB-1.1"}, None),
    ("authenticator codes after I replaced my phone", {"KB-003", "HB-1.2", "HB-1.3"}, None),
    ("VPN connected but internal sites do not open", {"KB-007", "HB-2.3"}, None),
    ("what is the guest wifi network", {"KB-005", "HB-2.1"}, None),
    ("black flickering display", {"KB-010"}, None),
    ("how long until my approved software appears", {"KB-015"}, None),
    ("I clicked a phishing link", {"KB-020"}, None),
    ("who approves a shared mailbox request", {"KB-022"}, None),
    ("security key for payments", {"KB-024"}, None),
    ("printer offline", {"KB-012"}, {"team": "hardware"}),
    ("HDMI", {"KB-013"}, None),
]


@lesson("03.5/3", "Acceptance check")
def main(ctx):
    records = load_records()
    by_id = {r["id"]: r for r in records}
    client, collection = build_collection(ctx, records)

    ctx.step("Hit@3 per mode (is an acceptable record in the top 3?)")
    results = {}
    for mode in ("vector", "bm25", "hybrid"):
        hits = 0
        for question, ok, where in CASES:
            top = search(ctx, collection, records, question, k=3, where=where, mode=mode)
            hits += bool(ok & set(top))
            results[(mode, question)] = top
        ctx.note(f"{mode:<7} {hits}/{len(CASES)}")
        results[mode] = hits

    ctx.step("Acceptance criteria")
    leaks = search(ctx, collection, records, "hardware security key", k=5, where={"audience": "finance"})
    checks = [
        ("hybrid finds an acceptable record in the top 3 for at least 10 of 12 questions", results["hybrid"] >= 10),
        ("hybrid is at least as good as BM25 alone", results["hybrid"] >= results["bm25"]),
        ("a filtered search returns only records that match the filter", all(by_id[i]["audience"] == "finance" for i in leaks)),
        ("every record has source, team and audience metadata", all(r.get("source") and r.get("team") and r.get("audience") for r in records)),
    ]
    for text, passed in checks:
        ctx.note(f"[{'PASS' if passed else 'FAIL'}] {text}")

    ctx.step("Misses (hybrid)")
    missed = [q for q, ok, w in CASES if not (ok & set(results[("hybrid", q)]))]
    ctx.note("none" if not missed else "; ".join(missed))
    client.delete_collection(collection.name)


if __name__ == "__main__":
    main()
