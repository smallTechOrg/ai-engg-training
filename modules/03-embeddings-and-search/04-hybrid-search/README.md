# 03.4 · Hybrid search: keywords plus vectors

**Module:** [03 · Embeddings and semantic search](../README.md) · **Time:** 45-60 minutes · **Model needs:** embeddings (no chat model) · **Packages:** `rag` extra (`rank_bm25`)

## What you will learn

- How **BM25** keyword search scores documents, and where it beats or loses to vectors.
- Why BM25 scores and cosine scores cannot simply be added.
- **Reciprocal Rank Fusion (RRF)**: combine two rankings using only positions, and what the constant `k` does.
- How to **measure** whether hybrid search helps, and the traps (zero-score ties, stop words, tiny test sets).

## The idea

**What is new since 03.3:** one store, one signal (vectors). Vectors are weak at exact strings: an error
code, a product name, a rare acronym. Keyword search is the opposite: perfect on exact words, blind to
paraphrase. A hybrid runs both and merges the lists.

```mermaid
flowchart LR
    Q[query] --> B[BM25 keyword ranking]
    Q --> V[vector ranking]
    B --> F[RRF: 1/(k+rank) summed per document]
    V --> F
    F --> R[final ranking]
```

**BM25** gives a document a high score for sharing rare query words, with diminishing returns for repeats
and a length correction. **RRF** gives each document `1 / (k + rank)` from every ranking and adds them;
`k = 60` is the common default. Because only ranks are used, no score normalisation is needed.

## Scripts

Run all three with `./run 03.4` (Windows: `run 03.4`), or one at a time. No chat model is called.
`kb.json` is the same 24 invented knowledge-base articles as 03.3.

### 1. `01_bm25_vs_vectors.py`: two rankers, side by side

```
./run 03.4/1
```

Four queries ranked by `rank_bm25.BM25Okapi` and by embeddings.

**Expected output** (trimmed):

```
Step 4: Query: somebody took my handset
BM25: no article shares a word with the query (all scores 0).
Vector #1 ( 0.73) KB-011 Report a lost or stolen phone or laptop to IT at once so it
Step 5: Query: can't sign in after typing my password wrong
BM25   #1 ( 4.24) KB-002 An account locks after five wrong password attempts. ...
Vector #1 ( 0.72) KB-002 An account locks after five wrong password attempts. ...
```

The exact-word queries (`HDMI`, `Larkspur-Visitor`) are found by both: with a clean 24-article
set vectors are good at those too. BM25's guaranteed advantage appears on large collections full of
near-duplicates, where the exact token is the only thing that separates them.

### 2. `02_reciprocal_rank_fusion.py`: fuse by rank

```
./run 03.4/2
```

Fuses the two rankings for a VPN question, shows each document's rank in both lists, then varies `k`
and tries a weighted RRF.

**Expected output** (trimmed):

```
#1 KB-006 fused 0.0328  (BM25 rank 1, vector rank 1)  Install the Larkspur VPN client ...
#2 KB-007 fused 0.0323  (BM25 rank 2, vector rank 2)  If the VPN connects but internal sites ...
#3 KB-010 fused 0.0308  (BM25 rank 3, vector rank 7)  A flickering or black laptop screen ...
k=1    top 3: ['KB-006', 'KB-007', 'KB-010']  scores [1.0, 0.6667, 0.375]
k=1000 top 3: ['KB-006', 'KB-007', 'KB-010']  scores [0.002, 0.002, 0.002]
```

Here both rankers agree, so `k` and weights change nothing in the order. They matter when the rankers disagree.

### 3. `03_helpdesk_hybrid_eval.py`: does it help? Measure.

```
./run 03.4/3
```

Eleven questions with a known answer article, ranked by BM25, vectors, RRF, and RRF0 (zero-score
BM25 documents dropped before fusing). The last question uses a team filter applied before ranking.

**Expected output** (trimmed):

```
method    top-1  top-3  mean rank
bm25       9/11   9/11       4.00
vec       11/11  11/11       1.00
rrf        9/11   9/11       2.09
rrf0      10/11  11/11       1.09
```

An honest, slightly surprising result: on this small, clean knowledge base **vectors alone win**, and plain
RRF is *worse* than vectors. The cause: when BM25 matches no word of the right article its order is an
arbitrary tie, and RRF lets that noise vote. Dropping zero-score documents (RRF0) fixes most of it.
Hybrid pays off with exact codes, names and jargon; verify before you adopt it.

## Try this

1. In script 3 remove the `STOP` list from `tokens`. How do BM25's ranks change, and why?
2. Add a question containing a rare exact token (invent an error code, add an article that mentions it) and see which method finds it.
3. Change RRF's `k` in script 3 to 5 and to 500. Do the totals move?
4. Weight vectors 2x and BM25 0.5x in script 3's fusion. Is that better than RRF0 on these questions?
5. Write five more questions with their answers; does the ranking of methods stay the same?
6. Swap `BM25Okapi` for `BM25Plus` from `rank_bm25` and compare.

## If it does not work

Run `./run doctor`; it checks the `rag` extra (`rank_bm25` is part of it) and the embedding backend.
Install with `uv sync --extra rag` (or the command `./run doctor` shows).

## In the running scenario

Helpdesk questions mix paraphrase ("somebody took my handset") with exact strings (error codes,
network names). A hybrid with zero-score guards is the safe default, and a small labelled test set,
as in script 3, is how you decide. The capstone builds the knowledge-base search with filters and a
check.

**Next:** 03.5 · Capstone: semantic search over the helpdesk knowledge base (planned)
