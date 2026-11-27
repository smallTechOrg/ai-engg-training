"""Knowledge base and retrieval.

Pages are markdown files with a small header (id, title, effective, status). Superseded pages are
not searched, so an old policy cannot beat the current one. Search is lexical: the share of the
question's content words found in the page. If you pass an `embed` function (texts -> vectors) the
ranking also uses cosine similarity; the evidence gate always uses the lexical share, because
embedding scores of unrelated text are never near zero.
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

STOPWORDS = set("""a an the is are was were be do does did can could should would will how what when where who which why
i me my we our you your it its of to in on for with at by from and or not any there this that about
please need want know tell get larkspur labs""".split())


def words(text):
    """Lowercase content words with crude plural/ending stripping ('wi-fi' and 'wifi' match)."""
    text = text.lower().replace("-", "")
    out = []
    for word in re.findall(r"[a-z0-9]+", text):
        if word in STOPWORDS:
            continue
        for ending in ("ing", "ed", "es", "s"):
            if len(word) > 4 and word.endswith(ending):
                word = word[: -len(ending)]
                break
        out.append(word)
    return out


@dataclass
class Passage:
    id: str
    title: str
    text: str
    status: str = "current"
    effective: str = ""


@dataclass
class Hit:
    passage: Passage
    coverage: float  # share of the question's content words found in the passage (0..1)
    cosine: float | None  # None when no embedder is used
    score: float


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class KnowledgeBase:
    def __init__(self, directory, embed=None):
        self.passages = []
        for path in sorted(Path(directory).glob("*.md")):
            header, _, body = path.read_text(encoding="utf-8").partition("\n\n")
            meta = dict(line.split(": ", 1) for line in header.splitlines() if ": " in line)
            if meta.get("status", "current") != "current":
                continue  # an old policy must never be quoted as the answer
            self.passages.append(Passage(meta["id"], meta.get("title", path.stem), body.strip(), meta.get("status", "current"), meta.get("effective", "")))
        self.embed = embed
        self.vectors = embed([p.title + ". " + p.text for p in self.passages]) if embed else None

    def ids(self):
        return {p.id for p in self.passages}

    def search(self, query, k=3):
        query_words = set(words(query))
        query_vec = self.embed([query])[0] if self.embed else None
        hits = []
        for index, passage in enumerate(self.passages):
            page_words = set(words(passage.title + " " + passage.text))
            coverage = len(query_words & page_words) / len(query_words) if query_words else 0.0
            cos = cosine(query_vec, self.vectors[index]) if query_vec is not None else None
            hits.append(Hit(passage, coverage, cos, coverage + (0.3 * cos if cos is not None else 0.0)))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:k]
