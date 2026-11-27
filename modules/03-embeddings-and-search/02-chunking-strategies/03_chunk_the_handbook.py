"""03.2/3  Chunk the helpdesk handbook with headings and overlap

The helpdesk version: split the handbook by its `##` headings first (so every chunk knows its
section), then cut long sections into overlapping pieces, and keep the heading as metadata.
Search returns the chunk plus where it came from, which is what a user needs to trust it.

Run it:   ./run 03.2/3          (Windows: run 03.2/3)
Needs the `rag` extra (local embedding model). No chat model is used.
"""

import re
from pathlib import Path

import numpy as np

from labkit import lesson

HANDBOOK = Path(__file__).with_name("handbook.md")
MAX_CHARS = 350
OVERLAP_SENTENCES = 1
TICKETS = [
    "I got a new phone and the login codes stopped working",
    "the screen on my laptop keeps going black",
    "VPN says connected but the wiki will not load",
    "need access to the finance shared folder",
]


def split_sections(text):
    """[(heading, body)] from '## Heading' blocks."""
    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    return [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts), 2)]


def chunk_section(body, max_chars=MAX_CHARS, overlap=OVERLAP_SENTENCES):
    """Pack whole sentences up to max_chars; the next chunk repeats the last `overlap` sentences."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", body.replace("\n\n", " ")) if s]
    chunks, current = [], []
    for sentence in sentences:
        if current and len(" ".join(current + [sentence])) > max_chars:
            chunks.append(" ".join(current))
            current = current[-overlap:] if overlap else []
        current.append(sentence)
    if current:
        chunks.append(" ".join(current))
    return chunks


@lesson("03.2/3", "Chunk the helpdesk handbook with headings and overlap")
def main(ctx):
    text = HANDBOOK.read_text(encoding="utf-8")

    ctx.step("Split by heading, then by sentences with overlap")
    records = []
    for heading, body in split_sections(text):
        for n, chunk in enumerate(chunk_section(body), start=1):
            records.append({"section": heading, "part": n, "text": chunk})
    ctx.note(f"{len(records)} chunks from {len({r['section'] for r in records})} sections")
    ctx.show_data("First two chunks (text + metadata)", records[:2])

    ctx.step("Embed the chunks")
    # The heading goes into the embedded text too: it tells the model what the chunk is about.
    vectors = np.array(ctx.embed([f"{r['section']}: {r['text']}" for r in records]))
    vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    ctx.step("Search with four new tickets")
    for ticket in TICKETS:
        q = np.array(ctx.embed([ticket])[0])
        q = q / np.linalg.norm(q)
        scores = vectors @ q
        best = np.argsort(-scores)[:2]
        ctx.note(f"Ticket: {ticket}")
        for rank, i in enumerate(best, start=1):
            r = records[i]
            ctx.note(f"  #{rank} ({scores[i]:.2f}) [{r['section']} / part {r['part']}] {r['text'][:100]}...")

    ctx.step("What to take away")
    ctx.note("Heading-aware chunks carry their source, so an answer can be cited and filtered.")
    ctx.note("The overlap sentence keeps an instruction from being split from its context.")


if __name__ == "__main__":
    main()
