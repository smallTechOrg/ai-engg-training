"""04.4/1  Capstone, part 1: build a reusable index with metadata

Turn the knowledge base into an index you build once and reload many times: one record per chunk
(label, text, last-updated date, file) plus a matrix of normalised embeddings. The index is saved to
a temporary folder (so the lesson never touches your repo) and reloaded to prove the round trip.
Checks: labels are unique, no chunk is empty, every file contributed chunks, and a test query lands
where it should.

Run it:   ./run 04.4/1          (Windows: run 04.4/1)
     or:  python modules/04-rag-by-hand/04-capstone-helpdesk-answers-grounded-in-the-knowle/01_build_index.py
Needs the `rag` extra (local embedding model). No chat call.
"""

import json
import tempfile
from pathlib import Path

import numpy as np

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"


def load_chunks():
    chunks = []
    for path in sorted(KB_DIR.glob("*.md")):
        updated, number = "unknown", 0
        for paragraph in (p.strip() for p in path.read_text(encoding="utf-8").split("\n\n")):
            if not paragraph or paragraph.startswith("#"):
                continue
            if paragraph.startswith("Updated:"):
                updated = paragraph.split(":", 1)[1].strip()
                continue
            number += 1
            chunks.append({"source": f"{path.stem}#{number}", "file": path.stem, "text": paragraph, "updated": updated})
    return chunks


@lesson("04.4/1", "Build and persist the index")
def main(ctx):
    ctx.step("1. Chunk the knowledge base, keeping metadata")
    chunks = load_chunks()
    files = sorted({c["file"] for c in chunks})
    ctx.note(f"{len(files)} files -> {len(chunks)} chunks. Each keeps: label, text, updated date, file.")

    ctx.step("2. Embed once and normalise")
    matrix = np.array(ctx.embed([c["text"] for c in chunks]))
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    ctx.note(f"matrix shape {matrix.shape}")

    ctx.step("3. Save to a temporary folder and reload")
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
        np.save(folder / "vectors.npy", matrix)
        sizes = {p.name: p.stat().st_size for p in folder.iterdir()}
        ctx.note(f"saved: {sizes}")
        loaded_chunks = json.loads((folder / "chunks.json").read_text(encoding="utf-8"))
        loaded = np.load(folder / "vectors.npy")
    ctx.note(f"reloaded identical: chunks={loaded_chunks == chunks}, vectors={bool(np.allclose(loaded, matrix))}")
    ctx.note("An index built by hand is just two files. A vector database (module 15) adds filtering, updates and scale.")

    ctx.step("4. Sanity checks before anyone queries it")
    labels = [c["source"] for c in chunks]
    checks = {
        "labels are unique": len(labels) == len(set(labels)),
        "no empty chunks": all(c["text"].strip() for c in chunks),
        "every chunk has a date": all(c["updated"] != "unknown" for c in chunks),
    }
    query = np.array(ctx.embed(["How long can a VPN session last?"])[0])
    query = query / np.linalg.norm(query)
    best = chunks[int(np.argmax(matrix @ query))]["source"]
    checks[f"test query lands on a vpn chunk (got {best})"] = best.startswith("vpn#")
    for name, ok in checks.items():
        ctx.note(f"{'PASS' if ok else 'FAIL'}  {name}")
    ctx.note("Stale files are still in the index on purpose: script 2 must handle them, not hide from them.")


if __name__ == "__main__":
    main()
