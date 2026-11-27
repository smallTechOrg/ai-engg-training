"""03.2/1  Three ways to cut a document

An embedding of a whole handbook is a blurry average. Search needs pieces. This script cuts
one handbook three ways (fixed size, sentences, recursive) and shows what each piece looks
like. No model is called, so it is instant and you can see exactly where the cuts fall.

Run it:   ./run 03.2/1          (Windows: run 03.2/1)
Needs nothing but the standard library.
"""

import re
from pathlib import Path

from labkit import lesson

HANDBOOK = Path(__file__).with_name("handbook.md")


def fixed_chunks(text, size=300, overlap=50):
    """Every `size` characters, stepping back `overlap` so a cut sentence appears twice."""
    step = size - overlap
    return [text[i:i + size].strip() for i in range(0, len(text), step) if text[i:i + size].strip()]


def sentence_chunks(text, per_chunk=3):
    """Split on sentence ends, then group `per_chunk` sentences."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    return [" ".join(sentences[i:i + per_chunk]) for i in range(0, len(sentences), per_chunk)]


def recursive_chunks(text, size=400, separators=("\n\n", "\n", ". ", " ")):
    """Try the biggest separator first; only split further what is still too long; then merge small pieces."""
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


def show(ctx, name, chunks):
    lengths = [len(c) for c in chunks]
    ctx.note(f"{name}: {len(chunks)} chunks, length min {min(lengths)} / avg {sum(lengths) // len(lengths)} / max {max(lengths)}")
    for i in (1, 2):
        ctx.note(f"  chunk {i}: {chunks[i][:110]!r}{'...' if len(chunks[i]) > 110 else ''}")
    ends = sum(1 for c in chunks if c[-1] in ".!?")
    ctx.note(f"  chunks that end at a sentence end: {ends} of {len(chunks)}")


@lesson("03.2/1", "Three ways to cut a document")
def main(ctx):
    text = HANDBOOK.read_text(encoding="utf-8")
    ctx.step("The document")
    ctx.note(f"handbook.md: {len(text)} characters, {len(text.split())} words")

    ctx.step("1. Fixed size: 300 characters, 50 overlap")
    show(ctx, "fixed", fixed_chunks(text))
    ctx.note("Simple and predictable, but it cuts mid-word and mid-sentence.")

    ctx.step("2. Sentences: 3 per chunk")
    show(ctx, "sentence", sentence_chunks(text))
    ctx.note("Every chunk is whole sentences, but sizes vary and headings get glued to text.")

    ctx.step("3. Recursive: split on paragraphs, then lines, then sentences, then words")
    show(ctx, "recursive", recursive_chunks(text))
    ctx.note("Respects the document's own structure and keeps chunks under the limit.")


if __name__ == "__main__":
    main()
