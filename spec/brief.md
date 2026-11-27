# Brief

A client-neutral teaching repository that takes upskilling professionals from a first
LLM call to agents, RAG, MCP, LangChain, LangGraph, CrewAI and the infrastructure topics
around them (serving, deployment, monitoring, guardrails, workflow automation).

**Who uses it and how.** The instructor demos lessons live; learners clone the repo and
follow along on their own machines; the same learners return to it for self-study; the
material is reused across cohorts while libraries keep changing.

**Interaction model.** One `main` branch. Modules contain lessons of 45-60 minutes. A
lesson is a folder holding a concept README (flow diagram, expected output, try-this
experiments) and numbered, plainly runnable Python scripts. Each lesson shows the bare
concept first, then applies it to one running scenario (an IT helpdesk assistant); each
module ends with a capstone on that scenario. Lessons never import each other; a small
shared package (`labkit`) holds plumbing only.

**Capabilities.** Bootstrap with no pre-existing Python; a launcher (numbered menu, list
with status); a doctor command (Python, packages, `.env`, a real endpoint call, model
capabilities, infra services, optional report file); lesson output with labelled steps,
messages sent and received, tool calls, tokens per call and per run, streaming answers,
`--raw` wire dump, and a log file per run; friendly errors instead of stack traces.

**Hard constraints.** Portable: macOS, Windows, Linux, VMs. Any OpenAI-compatible
endpoint, from hosted models to small local ones; lessons state the minimum capability
they need. Infra-backed lessons address services through `.env` (container, native
install or cloud) and skip cleanly when a service is missing. Pinned lockfile; CI on
three operating systems; a live check to run before each cohort.

**Phase 1 core path.** `setup` -> `run doctor` -> `run 01.1` prints a real model reply.

## Assumptions

- Assumed: phases are sequenced as tooling + skeleton + map + one working lesson, then
  Foundations complete, then one thin script per module, then depth (the user selected
  all of these for "first"; the smallest testable slice goes first).
- Assumed: by-hand modules (tools/agents, RAG in plain Python) precede the frameworks.
- Assumed: scripts inside a lesson are numbered `01_`, `02_`, ...
- Assumed: the embeddings model is a separate setting defaulting to the chat endpoint.
- Assumed: heavy frameworks are optional extras installed per module group.
- Assumed: CI uses a local stub of the OpenAI-compatible API (no secrets in CI).
- Assumed: the menu is number-driven (works in every terminal, including VMs).
