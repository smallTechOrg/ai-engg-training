# AI-native design

## Does the product itself need an AI capability?

**No — reasoned conclusion.** The tooling (bootstrap, launcher, doctor, curriculum map,
live check) must be deterministic, fast, free to run and trustworthy on a broken machine.
An LLM in that path would add cost, latency and a dependency on the very thing the doctor
is diagnosing. Diagnostics are rule-based: each failure maps to one plain-language fix.

AI is the **subject matter**. The design duty is therefore that lessons demonstrate the
patterns correctly and in an order that builds understanding.

## Patterns taught, in order

| Pattern | First shown by hand | Then with a framework |
|---|---|---|
| Single call, roles, streaming, parameters | 01 Foundations | 06 LangChain core |
| Prompt engineering, structured output | 01 Foundations | 06 |
| Tool calling | 02 Tools and agents by hand | 07 LangChain agents |
| Agent loop (reason-act-observe), memory | 02 | 07, 08 LangGraph |
| Embeddings, semantic search | 03 | 06 |
| RAG | 04 RAG by hand | 06, 15 Agentic RAG |
| Routing, state machines | — | 08 LangGraph |
| Cycles, self-correction, human-in-the-loop, persistence | — | 09 LangGraph |
| Tracing and evaluation | console trace in `labkit` | 10 |
| Tool/data protocol (MCP) | 11 custom server | 12 ecosystem |
| Reflection, planning, long-term memory | 13 | 13 |
| Multi-agent roles | — | 14 CrewAI |
| Guardrails | — | 18 |

## Rules for lesson code that calls a model

- One batched call per artifact; never a model call per output line or token.
- Every loop that calls a model has a hard iteration cap, printed when hit.
- Small prompts that ask for short answers, so a cohort run costs pennies. No
  `max_tokens` by default: providers disagree on the parameter name.
- Lessons state their minimum capability; they degrade with an explanation, not a crash.
- The running scenario uses invented helpdesk data only.
