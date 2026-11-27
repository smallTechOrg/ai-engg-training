# 13.1 · Reflection: generate, critique, revise

**Module:** [13 · Deep agents: reflection, planning, long-term memory](../README.md) · **Time:** 45-60 minutes · **Model needs:** chat (JSON output helps) · **Packages:** `langgraph` extra (scripts 2 and 3)

## What you will learn

- What **reflection** is: a model checks its own output against a written standard, then fixes it.
- How to write a **rubric** a model can score (1-5 per criterion, as JSON).
- How to turn the pattern into a **loop** with two stop rules: a quality bar and a hard round cap.
- Why reflection is not planning (13.2) and not memory (13.3).

## The idea

A first draft is rarely the best the model can do, and models are often better at *judging* text
than at writing it right the first time. Reflection exploits that: draft, critique against a
rubric, revise, and repeat until the text clears a bar.

```mermaid
flowchart LR
    G[generate draft] --> C[critique vs rubric]
    C -->|average below bar and rounds left| R[revise]
    R --> C
    C -->|bar met or round cap hit| D([done])
```

How it differs from the other two ideas in this module:

- **Reflection** improves *one piece of work* by looping over it. Nothing is remembered afterwards.
- **Planning** (13.2) decides *which steps to take* before and during a task.
- **Long-term memory** (13.3) keeps what was learned *across* tasks and sessions.

Two cautions. The critic is a model too, so it can be generous (in our runs it often gave 5s to a
first draft), which is why the rubric must be specific and the critic told to be harsh. And every
loop that calls a model needs a hard cap, because "until it is good enough" may never happen.

## Scripts

Run all three with `./run 13.1` (Windows: `run 13.1`), or one at a time.

### 1. `01_reflect_by_hand.py`: one round in plain Python

```
./run 13.1/1
```

Draft, critique (JSON scores per criterion), revise, then score the revision with the same
rubric and print before and after. Four model calls through `ctx.client`, no framework.

**Expected output** (trimmed; scores and wording will differ):

```
Step 2: Critique the draft against the rubric
Scores and feedback
{
  "scores": { "clarity": 5, "actionability": 5, "tone": 4 },
  "feedback": "The message is clear and direct, though it could be slightly warmer ..."
}

Step 4: Score the revision with the same rubric
Scores before -> after
{ "clarity": "5 -> 5", "actionability": "5 -> 5", "tone": "4 -> 4" }
Average: 4.7 -> 4.7

Run summary: 4 model call(s), 528 in + 228 out = 756 tokens, 6.0s
```

Note that one round can leave the scores unchanged: reflection is not guaranteed to improve
anything, which is why you measure.

### 2. `02_reflect_loop_graph.py`: the same thing as a LangGraph loop

```
./run 13.1/2
```

Nodes `generate`, `critique`, `revise`; a conditional edge after `critique` ends the run when
the average reaches 4.8 or after 3 critiques. (The graph machinery is from module 08.)

**Expected output** (trimmed):

```
Stops when the average score >= 4.8 or after 3 critiques, whichever comes first.
generate: wrote a new draft (61 words)
critique #1: average 4.67 - The message is clear and provides immediate, helpful steps ...
revise: wrote a new draft (60 words)
critique #2: average 4.67 - ...
revise: wrote a new draft (60 words)
critique #3: average 4.67 - ...

Average score after each critique
[ 4.67, 4.67, 4.67 ]
Hit the cap of 3 critiques without reaching 4.8; returning the latest draft.

Run summary: 6 model call(s), 861 in + 345 out = 1206 tokens, 11.8s
```

Hitting the cap is a normal, explained outcome, and it shows why the cap exists.

### 3. `03_helpdesk_knowledge_article.py`: a knowledge-base article to a quality bar

```
./run 13.1/3
```

The scenario: a recurring ticket (lockout after a password change, caused by a phone retrying
the old password). Write the article that deflects it, review it against a four-criterion
rubric (findable, complete, followable, concise), revise, and either publish or flag for a human.

**Expected output** (trimmed):

```
Step 2: Write, review, revise
write: new draft (207 words)
review #1: {'findable': 5, 'complete': 4, 'followable': 5, 'concise': 4} average 4.50
   editor: The guide is excellent, but it should explicitly state that ...
revise: new draft (235 words)
review #2: ... average 4.25
revise: new draft (195 words)
review #3: ... average 4.50

Average score per review
[ 4.5, 4.25, 4.5 ]
Did not clear the bar within the cap: send to a human editor with the feedback above.
```

Scores can go down as well as up: each revision fixes one thing the critic named and may
disturb another. The loop stops by rule, not by hope.

## Try this

1. In script 1, remove the "harsh reviewer" wording from `CRITIC_SYSTEM` and compare the scores.
2. In script 2, set `THRESHOLD = 4.0`. How many rounds now?
3. Add a fourth rubric criterion to script 3 (for example "mentions how to avoid it next time") and watch which feedback the critic returns.
4. In script 2, keep only the best-scoring draft instead of the latest one (add `best_draft` to the state).
5. Make `MAX_ROUNDS = 1` and compare the cost in tokens with `MAX_ROUNDS = 3`.
6. Use a different `LLM_MODEL` for the critic than for the writer, if your endpoint has two.

## If it does not work

- Run `./run doctor` to check the endpoint and installed extras.
- `ModuleNotFoundError: langgraph`: install the extra with `uv sync --extra langgraph` (scripts 2 and 3).
- If the critic returns text that is not JSON, the lesson treats it as an unusable critique: script 1 says so, scripts 2 and 3 score it 0 and keep going until the cap.

## In the running scenario

The helpdesk assistant gets a quality gate for what it publishes. An article about a repeating
issue is only worth deflecting tickets if it is findable and followable, so it is written,
reviewed against that standard and either published or sent to a person. 13.2 adds planning
and 13.3 memory, so the assistant can remember which articles resolved which tickets.

**Next:** 13.2 · Planning and replanning (planned)
