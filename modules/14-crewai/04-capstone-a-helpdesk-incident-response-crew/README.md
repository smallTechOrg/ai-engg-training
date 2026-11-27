# 14.4 · Capstone: a helpdesk incident-response crew

**Module:** [14 · CrewAI: multi-agent orchestration](../README.md) · **Time:** 45-60 minutes · **Model needs:** chat, tools · **Packages:** `crewai` and `langgraph` extras

## What you will learn

- How to combine typed hand-offs, a tool, a graph and a retry loop with a cap in one design.
- How to turn acceptance criteria (the conditions the result must meet) into checks that run on a crew's output.
- How to keep a crew's request count inside a budget.

## The idea

This lesson adds nothing new. It combines everything from the module. When an incident comes in, a
crew triages it, finds the runbook steps (the agreed fix-it instructions) and writes the message to
staff. A LangGraph guard checks the message and sends it back for another try at most once.

**Brief.** Larkspur Labs wants a first status message within a minute of an incident report.

**Acceptance criteria.**
1. Severity is a typed field (`low`, `medium`, `high`). An incident that blocks many people or a deadline is `high`.
2. The message uses the runbook steps, not invented ones.
3. The message mentions the status page and has at most four sentences.
4. A crew that only triages and writes (no tool) stays within 8 model requests. Adding the researcher with its tool costs more (script 1 used 12), so state your budget.
5. Every loop has a cap, and a person reviews any message that still fails after the cap.

**Stretch goals.**

- Add a fourth agent that reviews the message.
- Route low-severity incidents to one plain call (14.3/3).
- Add a runbook entry and test it.
- Save the graph state with a checkpointer.

```mermaid
flowchart LR
    I[Incident] --> T[Triager: typed Severity]
    T --> R[Researcher: search_runbook]
    R --> W[Comms writer]
    W --> G{Guard: status page, 4 sentences}
    G -- ok --> D[Done]
    G -- bad, runs < 2 --> W
    G -- bad, cap reached --> H[Human review]
```

## Scripts

Run all three with `./run 14.4`. `runbook.json` is the made-up runbook the researcher reads.

### 1. `01_incident_crew.py`: the reference crew

```
./run 14.4/1
```

A sequential crew with a triager (using output_pydantic), a researcher (with a tool) and a writer.

**Expected output** (trimmed):

```
tool call | search_runbook({"topic": "VPN Connectivity"})
   result | VPN outage: 1) check the status page, 2) ask users to sign in again with their security key, ...
Severity (typed)
{ "severity": "High", "topic": "VPN Connectivity", "reason": "Approximately 40 employees ... " }
Status message
"We are currently investigating a VPN connectivity issue affecting the Berlin office. Please check the status page at ..."
requests and tokens
{ "successful_requests": 12, "total_tokens": 5853 }
```

In this run the model made up a status-page address. The runbook only says "the status page", so criterion 2 is not
fully met. That makes a good experiment for Try this.

### 2. `02_graph_with_a_guard_loop.py`: a guard and a capped retry

```
./run 14.4/2
```

A crew with one agent runs inside a graph. A guard written in plain Python checks the message. If the check fails,
the crew runs again with the problem added to the task. The crew runs at most twice.

**Expected output** (trimmed):

```
crew run 1: 1 request(s)
guard after run 1
{ "problems": ["does not mention the status page"], "message": "We are currently experiencing email delays ..." }
crew run 2: 2 request(s)
guard after run 2
{ "problems": "none", ... }
final: { "crew_runs": 2, "problems_left": "none", ... }
```

### 3. `03_acceptance_check.py`: acceptance criteria as code

```
./run 14.4/3
```

A triager and a writer handle an incident with a deadline. Six checks each print PASS or FAIL.

**Expected output** (trimmed):

```
PASS  typed severity parsed
PASS  severity is low/medium/high
PASS  deadline incident rated high
PASS  message mentions the status page
PASS  message at most four sentences
PASS  requests within budget (4 <= 8)
```

## Try this

1. In script 1, replace the incident with an email delay. Does the researcher pick the `email` entry?
2. Add a runbook entry to `runbook.json` and write an incident that needs it.
3. In script 1, add a check that every step number in the message appears in the runbook text (criterion 2).
4. In script 2, set `MAX_CREW_RUNS = 1`. What does the cap note say?
5. In script 3, make the incident low severity. Which checks should now fail, and do they?
6. Count the requests per agent. Which of the three costs the most in script 1?

## If it does not work

Run `./run doctor`. Install with `uv sync --extra crewai --extra langgraph`. A real model can fail a check.
That is a result, not a bug. With the offline stub model (a stand-in that returns canned replies), the checks
fail by design and the loops end on their caps.

## In the running scenario

Larkspur Labs now has an incident desk. It has a typed triage, a runbook lookup, a status message that must
pass a guard, and a test that says whether the crew meets the brief.

**Next:** 15.1 · RAG failure modes and how to diagnose them
