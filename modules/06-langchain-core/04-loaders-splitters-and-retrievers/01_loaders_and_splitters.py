"""06.4/1  Loaders and splitters: from files to Documents to chunks

RAG with LangChain starts with two small abstractions:

  Document        page_content (text) + metadata (a dict: where it came from)
  Loader          reads a source and returns a list of Documents (here `TextLoader`)
  Text splitter   cuts Documents into chunks and COPIES the metadata onto each chunk

No model is called in this script. Chunking is a design choice you can inspect for free: chunk size,
overlap and where the cuts fall decide what retrieval can find (compare lesson 04.1, which split on blank lines).

Run it:   ./run 06.4/1          (Windows: run 06.4/1)
"""

import warnings
from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from labkit import lesson

KB_DIR = Path(__file__).parent / "kb"


@lesson("06.4/1", "Loaders and splitters")
def main(ctx):
    ctx.step("Load: one Document per file")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # langchain-community announces its own sunset on import
        from langchain_community.document_loaders import TextLoader

    docs = []
    for path in sorted(KB_DIR.glob("*.md")):
        docs += TextLoader(str(path), encoding="utf-8").load()
    ctx.show_data("Documents loaded", [{"source": Path(d.metadata["source"]).name, "characters": len(d.page_content)} for d in docs])
    ctx.show_data("One Document", {"metadata": {"source": Path(docs[0].metadata["source"]).name}, "page_content": docs[0].page_content[:100] + "..."})
    for d in docs:
        d.metadata["source"] = Path(d.metadata["source"]).name  # keep just the file name as the citation label

    ctx.step("Split: RecursiveCharacterTextSplitter")
    ctx.note("It tries to cut at paragraph breaks, then lines, then spaces, then characters, to stay under chunk_size.")
    for size, overlap in [(1000, 0), (300, 0), (300, 60)]:
        splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
        chunks = splitter.split_documents(docs)
        lengths = [len(c.page_content) for c in chunks]
        ctx.note(f"chunk_size={size:<5} overlap={overlap:<3} -> {len(chunks)} chunks, longest {max(lengths)}, shortest {min(lengths)}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=60)
    onboarding = [d for d in docs if d.metadata["source"] == "onboarding.md"]
    chunks = splitter.split_documents(onboarding)
    ctx.show_data("onboarding.md as chunks (300/60): first three", [{"metadata": c.metadata, "text": c.page_content} for c in chunks[:3]])
    ctx.note("With overlap, the end of one chunk is repeated at the start of the next (see the repeated Day one heading), so text cut at an edge still appears whole in one chunk.")

    ctx.step("Split by structure: MarkdownHeaderTextSplitter")
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "title"), ("##", "section")])
    sections = header_splitter.split_text(onboarding[0].page_content)
    ctx.show_data("sections", [{"metadata": s.metadata, "characters": len(s.page_content)} for s in sections])
    ctx.note("The headings became metadata. Retrieval can show 'New starter IT checklist > Day one' as the citation.")
    ctx.note("Real systems often chain the two: split by headers first, then cap section length with the recursive splitter.")


if __name__ == "__main__":
    main()
