"""03.1/2  Semantic vs keyword search

Search a small helpdesk knowledge base two ways: counting shared words, and comparing
embeddings. A query that shares no words with the right article still finds it.

Run it:   ./run 03.1/2          (Windows: run 03.1/2)
     or:  python modules/03-embeddings-and-search/01-what-embeddings-are/02_semantic_vs_keyword.py
Needs the `rag` extra (local embedding model). No chat model is used.
"""

import re

import numpy as np

from labkit import lesson

KB = [
    "To reset your password, open the self-service portal and choose Forgot password.",
    "Connect to the VPN with the Larkspur client before opening internal tools from home.",
    "Laptops are replaced every four years; request a new one through your manager.",
    "If a printer shows offline, restart it and re-add it from the Printers page.",
    "Guests can join the visitor Wi-Fi network; the daily code is at the front desk.",
    "Request new software by filing a ticket with the business reason and cost centre.",
    "Report a lost or stolen phone to IT immediately so it can be wiped remotely.",
    "Shared mailboxes are created by IT; ask in the helpdesk channel with the team name.",
    "Two-factor codes come from the authenticator app; re-enrol it if you get a new phone.",
    "Meeting room screens support wireless casting; plug in the HDMI cable if casting fails.",
]
QUERIES = [
    "I cannot remember my login details",   # shares no words with the reset article
    "working from my flat and cannot reach the intranet",
    "someone took my handset on the train",
]
STOP = {"the", "a", "to", "and", "or", "i", "my", "if", "it", "is", "of", "in", "with", "from", "can", "not", "on", "for", "your", "so", "you"}


def words(text):
    return {w for w in re.findall(r"[a-z0-9-]+", text.lower()) if w not in STOP}


@lesson("03.1/2", "Semantic vs keyword search")
def main(ctx):
    ctx.step("The knowledge base")
    ctx.note(f"{len(KB)} invented Larkspur Labs snippets. Index them once.")
    doc_vectors = np.array(ctx.embed(KB))
    doc_vectors = doc_vectors / np.linalg.norm(doc_vectors, axis=1, keepdims=True)

    for query in QUERIES:
        ctx.step(f"Query: {query}")
        q_words = words(query)

        # Keyword search: count shared words.
        overlaps = [len(q_words & words(doc)) for doc in KB]
        if max(overlaps) == 0:
            ctx.note("Keyword search: no snippet shares a single word with this query. Nothing found.")
        else:
            k = int(np.argmax(overlaps))
            ctx.note(f"Keyword search: best match shares {overlaps[k]} word(s): {KB[k]}")

        # Semantic search: embed the query, rank by cosine similarity.
        q = np.array(ctx.embed([query])[0])
        q = q / np.linalg.norm(q)
        scores = doc_vectors @ q
        for rank, idx in enumerate(np.argsort(-scores)[:3], start=1):
            ctx.note(f"Semantic #{rank} ({scores[idx]:.2f}): {KB[idx]}")

    ctx.step("What to take away")
    ctx.note("Semantic search ranks by meaning, so paraphrases match. It always returns *something*:")
    ctx.note("the top score is a ranking, not proof of a good answer. Watch the numbers.")


if __name__ == "__main__":
    main()
