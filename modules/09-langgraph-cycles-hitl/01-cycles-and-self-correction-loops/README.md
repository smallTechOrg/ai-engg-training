# 09.1 · Cycles and self-correction loops

**Module:** [09 · LangGraph: cycles, human-in-the-loop, persistence](../README.md) · **Time:** 45-60 minutes · **Model needs:** chat · **Packages:** `langgraph` extra (`uv sync --extra langgraph`)

## What you will learn

- How a LangGraph graph loops: a node, a state, and a conditional edge that routes back or to `END`.
- What `recursion_limit` does and the error it raises when a loop does not stop.
- The generate, check, revise pattern, with a deterministic checker and with an LLM judge.
- Why every loop needs its own cap, printed when it is hit.

## The idea

A chain goes one way. A graph can go back. Self-correction is a loop: produce something,
check it, and if the check finds problems feed them back and produce again. Two things
make it safe: a checker that returns concrete problems, and a hard cap.

```mermaid
flowchart LR
    S([start]) --> G[generate]
    G --> C[check]
    C -->|problems and revisions < cap| G
    C -->|ok or cap reached| E([end])
```

The by-hand equivalent is a `for` loop around `client.chat.completions.create` (module 02).
The graph version makes the state and the routing explicit, which pays off in lessons 09.2 and 09.3.

## Scripts

Run all three with `./run 09.1` (Windows: `run 09.1`), or one at a time.

### 1. `01_counter_cycle.py`: a cycle and its limit (no model)

```
./run 09.1/1
```

One node adds 1 to a counter; a conditional edge loops until it reaches the target. A second
run uses an unreachable target with `recursion_limit=5` to show the loop being stopped.

**Expected output** (trimmed):

```
state = {'count': 0, 'target': 3}
state = {'count': 1, 'target': 3}
state = {'count': 2, 'target': 3}
state = {'count': 3, 'target': 3}
GraphRecursionError: Recursion limit of 5 reached without hitting a stop condition. ...
```

### 2. `02_generate_check_revise.py`: draft, check in Python, revise

```
./run 09.1/2
```

The model drafts a reply about ticket LL-2041. `check_reply` (plain Python) tests word count,
that the ticket id is mentioned, and forbidden phrases. Problems go back to the model as
feedback; at most 3 revisions. The limit is 35 words on purpose, so the model usually needs
more than one try.

**Expected output** (trimmed):

```
tokens: 44 in + 67 out = 111
[check] revision 0: 1 problem(s) ['too long: 48 words, limit is 35']
[route] problems found: back to generate with feedback
[check] revision 1: 1 problem(s) ['too long: 45 words, limit is 35']
...
[check] revision 3: 1 problem(s) ['too long: 39 words, limit is 35']
[route] cap of 3 revisions reached with problems left: stop anyway
The reply still has problems after the cap. A real system would hand it to a person.
Run summary: 4 model call(s), 448 in + 251 out = 699 tokens, 7.0s
```

### 3. `03_llm_judge_loop.py`: the checker is a model

```
./run 09.1/3
```

The same loop, but the checker is a second model call using `with_structured_output(Verdict)`
returning `{ok, problems}`. Capped at 2 revisions (6 model calls). If the judge returns
nothing parseable, the script treats it as "not ok" and carries on to the cap.

**Expected output** (trimmed):

```
[judge] ok=False problems=['The reply exceeds the 60-word limit.']
[route] judge rejected: revise
...
[route] cap of 2 revisions reached: stop with the last draft
Run summary: 6 model call(s), 1210 in + 371 out = 1581 tokens, 11.0s
```

Notice a judge can be wrong or stubborn; the cap is what makes the loop safe.

## Try this

1. In script 1, set `recursion_limit` to 3 with `target=3`. Does it finish? Count the steps.
2. In script 2, change the word limit to 80 and see the loop end at once.
3. In script 2, add a forbidden phrase the model is likely to use ("Best regards") and watch the feedback.
4. In script 2, set `MAX_REVISIONS = 0`. What happens?
5. In script 3, change the judge's `temperature` to 0.9. Is the verdict stable between runs?
6. In script 3, replace the judge's criteria in the `Verdict` field description and see how the verdicts change.

## If it does not work

- Run `./run doctor`. It checks the endpoint and the optional extras.
- `ModuleNotFoundError: langgraph`: install the extra with `uv sync --extra langgraph`.
- Script 3 shows "could not parse a verdict": the model may not support structured output well. The loop still ends at the cap.

## In the running scenario

The helpdesk assistant now checks its own replies before they go out: a cheap rule-based
check first, an LLM judge for what rules cannot see, and a cap so a stubborn draft ends up
with a person instead of looping forever.

**Next:** 09.2 · Human-in-the-loop: interrupt, approve, resume (planned)
