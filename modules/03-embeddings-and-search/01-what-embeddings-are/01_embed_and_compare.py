"""03.1/1  Embed and compare

Turn sentences into vectors, then measure how close they are: cosine similarity first in
plain Python (so nothing is hidden), then in numpy, then as a full similarity matrix.

Run it:   ./run 03.1/1          (Windows: run 03.1/1)
     or:  python modules/03-embeddings-and-search/01-what-embeddings-are/01_embed_and_compare.py
Needs the `rag` extra (local embedding model). No chat model is used.
"""

import math

import numpy as np

from labkit import lesson

SENTENCES = [
    "My laptop will not connect to the office Wi-Fi.",
    "I cannot get onto the wireless network at work.",
    "How do I reset my email password?",
    "The printer on floor 3 is out of paper.",
]


def cosine_plain(a, b):
    """Cosine similarity with nothing but the standard library."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


@lesson("03.1/1", "Embed and compare")
def main(ctx):
    ctx.step("Embed a handful of sentences")
    ctx.note("An embedding model maps each text to a list of numbers (a vector). One call, many texts.")
    # ctx.embed uses a local model by default, or a hosted one if EMBEDDING_MODEL is set.
    vectors = ctx.embed(SENTENCES)
    for sentence, vector in zip(SENTENCES, vectors):
        first = ", ".join(f"{x:+.3f}" for x in vector[:5])
        ctx.note(f"{len(vector)} numbers: [{first}, ...]  <-  {sentence}")

    ctx.step("Cosine similarity by hand")
    ctx.note("cosine = dot(a, b) / (|a| * |b|). 1.0 = same direction, 0 = unrelated, negative = opposed.")
    ctx.note("Compare sentence 0 (Wi-Fi) with the others, using only math and zip().")
    for i in (1, 2, 3):
        score = cosine_plain(vectors[0], vectors[i])
        ctx.note(f"{score:.3f}  {SENTENCES[0]!r} vs {SENTENCES[i]!r}")

    ctx.step("The same thing in numpy")
    a, b = np.array(vectors[0]), np.array(vectors[1])
    numpy_score = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    plain_score = cosine_plain(vectors[0], vectors[1])
    ctx.note(f"plain Python: {plain_score:.6f}    numpy: {numpy_score:.6f}")
    ctx.note("Many embedding models return unit-length vectors, so the dot product alone equals the cosine.")
    ctx.note(f"Length of sentence 0's vector: {float(np.linalg.norm(a)):.4f}")

    ctx.step("A similarity matrix")
    matrix = np.array(vectors)
    matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    sims = matrix @ matrix.T  # every pair at once
    header = "      " + "".join(f"  s{j}  " for j in range(len(SENTENCES)))
    print(header)
    for i, row in enumerate(sims):
        print(f"  s{i}  " + "".join(f" {v:.2f} " for v in row))
    for i, sentence in enumerate(SENTENCES):
        ctx.note(f"s{i} = {sentence}")
    best = max(((sims[i][j], i, j) for i in range(4) for j in range(i + 1, 4)))
    ctx.note(f"Closest pair: s{best[1]} and s{best[2]} ({best[0]:.2f}). They share almost no words, only meaning.")


if __name__ == "__main__":
    main()
