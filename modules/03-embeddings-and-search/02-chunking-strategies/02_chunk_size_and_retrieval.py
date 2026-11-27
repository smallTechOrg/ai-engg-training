"""03.2/2  Chunk size changes what you find

Same handbook, same queries, five chunk sizes. For each size we embed the chunks, search,
and check whether the top result contains the sentence that actually answers the question.
Small chunks are precise but lose context; big chunks carry context but blur the meaning.

Run it:   ./run 03.2/2          (Windows: run 03.2/2)
Needs the `rag` extra (local embedding model). No chat model is used.
"""

from pathlib import Path

import numpy as np

from labkit import lesson

HANDBOOK = Path(__file__).with_name("handbook.md")
SIZES = [100, 200, 400, 800, 1600]
# (query, a phrase that only the right passage contains)
QUERIES = [
    ("my account is blocked after typing the wrong password", "five wrong attempts"),
    ("what do I do if my phone is stolen", "wiped remotely"),
    ("internal sites will not open while I am at home", "disconnect, wait ten seconds"),
    ("how long until approved software shows up", "two working days"),
    ("laptop forced to lock because I ignored updates", "delaying more than three days"),
]


def recursive_chunks(text, size, separators=("\n\n", "\n", ". ", " ")):
    if len(text) <= size:
        return [text.strip()] if text.strip() else []
    if not separators:
        return [text[i:i + size] for i in range(0, len(text), size)]
    sep, rest = separators[0], separators[1:]
    pieces = []
    for part in text.split(sep):
        pieces.extend(recursive_chunks(part, size, rest) if len(part) > size else [part.strip()])
    merged, current = [], ""
    for piece in pieces:
        if not piece:
            continue
        if current and len(current) + len(piece) + 1 > size:
            merged.append(current)
            current = piece
        else:
            current = f"{current} {piece}".strip()
    if current:
        merged.append(current)
    return merged


def normalise(m):
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


@lesson("03.2/2", "Chunk size changes what you find")
def main(ctx):
    text = HANDBOOK.read_text(encoding="utf-8")
    query_vectors = normalise(np.array(ctx.embed([q for q, _ in QUERIES])))

    ctx.step("Embed the handbook at five chunk sizes")
    rows = []
    for size in SIZES:
        chunks = recursive_chunks(text, size)
        vectors = normalise(np.array(ctx.embed(chunks)))
        scores = query_vectors @ vectors.T
        hits, top_scores, top_lengths = 0, [], []
        for qi, (_, phrase) in enumerate(QUERIES):
            best = int(np.argmax(scores[qi]))
            hits += phrase in chunks[best]
            top_scores.append(scores[qi][best])
            top_lengths.append(len(chunks[best]))
        rows.append((size, len(chunks), hits, float(np.mean(top_scores)), int(np.mean(top_lengths))))

    ctx.step("Result: does the top chunk contain the answer?")
    ctx.note(f"{'size':>5} {'chunks':>7} {'hits':>6} {'avg top score':>14} {'avg top chunk chars':>20}")
    for size, n, hits, score, length in rows:
        ctx.note(f"{size:>5} {n:>7} {hits:>3}/{len(QUERIES)} {score:>14.3f} {length:>20}")

    ctx.step("What to take away")
    ctx.note("Check the 'hits' column and the chunk length together. Tiny chunks can match the topic")
    ctx.note("but lack the answer; huge chunks always contain it but are mostly other text, which an")
    ctx.note("LLM must then read (and pay for). The average score falls as chunks grow because a big")
    ctx.note("chunk is a blurrier average, not because retrieval got worse. Measure on your own questions.")


if __name__ == "__main__":
    main()
