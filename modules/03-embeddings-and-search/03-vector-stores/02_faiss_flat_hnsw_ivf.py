"""03.3/2  FAISS: exact search versus approximate indexes

FAISS is a library, not a database: it indexes bare vectors and returns row numbers. It shines
when you have many vectors and care about speed. Three index types, same data:

  Flat   exact search, compares the query with every vector (the baseline)
  HNSW   a graph of neighbours; fast, high recall, needs more memory
  IVF    groups vectors into clusters, searches only the nearest few; needs a training step

The helpdesk knowledge base is too small to show a difference, so part 2 uses 30,000
random clustered vectors (not real text) just to measure speed and recall honestly.

Run it:   ./run 03.3/2          (Windows: run 03.3/2)
Needs the `rag` extra (faiss-cpu + local embedding model). No chat model is used.
"""

import json
import time
from pathlib import Path

import faiss
import numpy as np

from labkit import lesson

KB = json.loads(Path(__file__).with_name("kb.json").read_text(encoding="utf-8"))
DIM = 384


def timed(fn):
    start = time.perf_counter()
    out = fn()
    return out, (time.perf_counter() - start) * 1000


@lesson("03.3/2", "FAISS: Flat vs HNSW vs IVF")
def main(ctx):
    ctx.step("Part 1: a Flat index over the real knowledge base")
    vectors = np.array(ctx.embed([a["text"] for a in KB]), dtype="float32")
    faiss.normalize_L2(vectors)  # unit length, so inner product == cosine similarity
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    ctx.note(f"index.ntotal = {index.ntotal}")
    q = np.array(ctx.embed(["my account is locked and I cannot sign in"]), dtype="float32")
    faiss.normalize_L2(q)
    scores, ids = index.search(q, 3)
    for score, i in zip(scores[0], ids[0]):
        ctx.note(f"  row {i} ({score:.2f}) {KB[i]['id']}: {KB[i]['text'][:70]}")
    ctx.note("FAISS returns row numbers. Keeping text and metadata aligned with those rows is your job.")

    ctx.step("Part 2: 30,000 synthetic vectors: speed and recall")
    rng = np.random.default_rng(7)
    centres = rng.normal(size=(60, DIM)).astype("float32")
    data = (centres[rng.integers(0, 60, 30000)] + 0.6 * rng.normal(size=(30000, DIM))).astype("float32")
    queries = (centres[rng.integers(0, 60, 200)] + 0.6 * rng.normal(size=(200, DIM))).astype("float32")
    faiss.normalize_L2(data)
    faiss.normalize_L2(queries)
    k = 10

    flat = faiss.IndexFlatIP(DIM)
    flat.add(data)
    (_, truth), flat_ms = timed(lambda: flat.search(queries, k))

    hnsw = faiss.IndexHNSWFlat(DIM, 32, faiss.METRIC_INNER_PRODUCT)
    _, hnsw_build = timed(lambda: hnsw.add(data))
    hnsw.hnsw.efSearch = 64

    quantizer = faiss.IndexFlatIP(DIM)
    ivf = faiss.IndexIVFFlat(quantizer, DIM, 100, faiss.METRIC_INNER_PRODUCT)
    _, ivf_build = timed(lambda: (ivf.train(data), ivf.add(data)))
    ivf.nprobe = 8

    def recall(found):
        return float(np.mean([len(set(found[i]) & set(truth[i])) / k for i in range(len(truth))]))

    (_, h_ids), h_ms = timed(lambda: hnsw.search(queries, k))
    (_, v_ids), v_ms = timed(lambda: ivf.search(queries, k))
    ctx.note(f"{'index':<6} {'build ms':>9} {'200 queries ms':>15} {'recall@10':>10}")
    ctx.note(f"{'Flat':<6} {'0':>9} {flat_ms:>15.1f} {1.0:>10.2f}")
    ctx.note(f"{'HNSW':<6} {hnsw_build:>9.0f} {h_ms:>15.1f} {recall(h_ids):>10.2f}")
    ctx.note(f"{'IVF':<6} {ivf_build:>9.0f} {v_ms:>15.1f} {recall(v_ids):>10.2f}")

    ctx.step("Part 3: turning the recall knob")
    for nprobe in (1, 4, 16):
        ivf.nprobe = nprobe
        (_, ids_), ms = timed(lambda: ivf.search(queries, k))
        ctx.note(f"IVF nprobe={nprobe:<2}  {ms:>6.1f} ms  recall {recall(ids_):.2f}")

    ctx.step("What to take away")
    ctx.note("Flat is exact and fine up to roughly 100,000 vectors. Beyond that, HNSW trades memory and")
    ctx.note("build time for speed; IVF trades a training step and a tunable nprobe. Timings depend on")
    ctx.note("your machine, and random vectors are not text: measure on your own embeddings.")


if __name__ == "__main__":
    main()
