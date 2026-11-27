# 09.4 · Parallel workers and sub-graphs

**Module:** [09 · LangGraph: cycles, human-in-the-loop, persistence](../README.md) · **Time:** 45-60 minutes · **Model needs:** chat · **Packages:** `langgraph` extra (`uv sync --extra langgraph`)

## What you will learn

- Static parallel branches, and the `Send` API for a number of workers decided at run time.
- Why parallel writes to one state key need a reducer (`Annotated[list, operator.add]`).
- Running one model call per item in parallel and collecting the answers.
- Packaging a loop as a sub-graph, two ways to attach it, and `stream(..., subgraphs=True)`.

## The idea

**What is new since 09.3:** every graph so far did one thing at a time. Two extensions: do many things
in the same step (fan-out and fan-in), and nest one graph inside another (a sub-graph).

```mermaid
flowchart LR
    S([start]) -->|Send per ticket| W1[worker]
    S --> W2[worker]
    S --> W3[worker]
    W1 --> J[collect]
    W2 --> J
    W3 --> J
    J --> E([end])
```

`Send("worker", payload)` starts a worker with its own private input. The reducer on the shared state key
merges what the workers return. By hand this is a loop of `create()` calls, or `asyncio.gather` from
module 05; the graph version keeps the checkpointing and tracing you have already seen.

## Scripts

Run all three with `./run 09.4` (Windows: `run 09.4`), or one at a time.

### 1. `01_fan_out_fan_in.py`: Send and reducers (no model)

```
./run 09.4/1
```

Static branches first, then a dynamic fan-out of four workers that sleep 0.2 s each, then the empty case.

**Expected output** (trimmed):

```
notes: ['mail ok', 'vpn ok', 'joined after 2 checks']
[fan_out] 4 tickets -> 4 Send() objects
[collect] got 4 results
results: LL-3001..LL-3004 handled
4 workers of 0.2s each took 0.21s: they ran in parallel (sequential would be 0.8s).
[fan_out] 0 tickets -> 0 Send() objects
no tickets -> results = []
```

The order of `notes` (mail before vpn) is not guaranteed; do not depend on it. With an empty Send list nothing runs, not even `collect`.

### 2. `02_parallel_ticket_triage.py`: one model call per ticket, in parallel

```
./run 09.4/2
```

Five tickets, five classifications at once, then a plain-Python summary. The model's answer is mapped onto the
allowed categories by `normalise`, anything else becomes `other`.

**Expected output** (trimmed):

```
[worker] LL-3105 -> other (model said: 'other')
wall time for 5 model calls: 2.6s (they overlap)
summary: {"hardware": 1, "account": 1, "network": 1, "software": 1, "other": 1}
Run summary: 5 model call(s), 180 in + 5 out = 185 tokens, 2.7s
```

### 3. `03_subgraph_reply_drafter.py`: a graph inside a graph

```
./run 09.4/3
```

A drafter graph (write, check word count, revise at most once) is used by a parent that picks a tone. Attached
two ways: wrapped in a function (private state, keys mapped by hand) and added directly (shared keys). Streaming
with `subgraphs=True` tags each event with its namespace.

**Expected output** (trimmed):

```
nodes: write, check
"tone": "calm and quick, acknowledge urgency"
[inside drafter] node 'write' wrote keys ['draft', 'revisions']
[inside drafter] node 'check' wrote keys ['problems']
[parent] node 'drafter' wrote keys ['brief', 'draft', 'problems', 'revisions']
Run summary: 4 model call(s), 336 in + 326 out = 662 tokens, 6.2s
```

## Try this

1. In script 1, remove the reducer from `results` and read the `InvalidUpdateError`.
2. In script 1, change the sleep to 1 second. How does the total change with 4 and with 8 tickets?
3. In script 2, add a sixth ticket and a sixth category. Do you need to change the graph?
4. In script 2, make `normalise` stricter (return `unknown` for unrecognised answers) and see what a chatty model does to it.
5. In script 3, set `WORD_LIMIT = 10` and watch the sub-graph loop to its cap.
6. In script 3, give the sub-graph a checkpointer of its own and compare with letting it inherit the parent's.

## If it does not work

- Run `./run doctor`. It checks the endpoint and the optional extras.
- `ModuleNotFoundError: langgraph`: `uv sync --extra langgraph`.
- Rate-limit errors in script 2: the provider may not like five simultaneous calls. Lower the ticket count.
- An empty fan-out ends the graph before the join node. Handle the empty case before the graph if you need an output.

## In the running scenario

The helpdesk assistant triages a morning's tickets in parallel and reuses one reply-drafting
sub-graph wherever a reply is needed.

**Next:** 09.5 · Capstone: helpdesk change request with an approval gate
