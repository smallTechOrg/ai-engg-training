# Build journal

A log of friction with the build harness and runtime (not an app changelog).
Each entry: symptom -> what was done -> durable lesson.

## Run started 2026-11-27 10:26 IST

1. **No delegation roles or support tree available.** The build skill expects a
   `project-builder` sub-agent and a `support/` folder of role files and patterns; neither
   was installed alongside the skill. -> Ran spec-writer, generator and auditor roles
   inline from the skill text. -> Lesson: the skill should ship its support tree, or state
   up front that inline is the only mode.

2. **Reference material arrived mid-intake.** A planning spreadsheet was mentioned after
   round 2 and changed the questions worth asking (syllabus fit, infra modules).
   -> Read it before round 3 and adapted. -> Lesson: intake round 1 should ask "is there an
   existing syllabus or reference document?".

3. **Public repo + private reference file.** The repo is public and the reference file's
   name identifies a client. -> Ignored it with a generic `*.xlsx` rule so even
   `.gitignore` does not carry the name. -> Lesson: check repo visibility before writing
   ignore rules or notes that could name private material.

4. **"Pick everything" on the Phase 1 question.** All four first-phase options were
   selected. -> Sequenced them into phases, smallest testable slice first, recorded as an
   assumption. -> Lesson: phrase that question as an ordering, not a multi-select.

5. **SDK changed its HTTP library.** `import httpx` failed: the installed openai SDK
   (3.x) ships `httpx2`. -> Built the client via `openai.DefaultHttpxClient`. -> Lesson:
   inspect the installed version of a fast-moving SDK before writing against it from memory.

6. **Key present but dead.** `.env` existed with a placeholder key; the endpoint answered
   401. -> Built and tested against a local stub of the API, then re-ran the real gate
   once the key was filled in. -> Lesson: a stub endpoint keeps the build moving while a
   secret is pending, and doubles as the CI backend.

7. **Docker not installed on the build machine.** Infra modules (16-19) cannot be gated
   locally. -> Deferred to their phase; flagged to the user.

8. **A test passed on macOS/Linux and failed on Windows.** A subprocess with no stdin got
   the NUL device, which Windows reports as a terminal, so the launcher opened its menu.
   -> Tests now pass an empty pipe as stdin. -> Lesson: "is this a terminal?" checks need a
   three-OS CI run; local green is not evidence for Windows.

9. **Changing model mid-build stranded the running workers.** Sub-agents keep the model
   they started with; the user switched the session model to save tokens while three
   writers were running. -> Stopped them, audited what they had left on disk (24 scripts,
   4 finished READMEs: all passed stub and real runs), and relaunched only the remaining
   work on the new model. -> Lesson: workers that write durable files in disjoint folders
   make a stop-and-restart cheap; brief replacements with "these files already exist".

10. **A worker pasted edited output.** It replaced masked forms of invented example keys
    with placeholders, so the README would not match what learners see. -> Restored the
    real masks for invented keys; only the learner's own key stays a placeholder.
    -> Lesson: tell writers which values are sensitive (real settings) and which are not
    (invented demo data).

11. **Writers on a stale API brief.** The installed frameworks were far newer than model
    memory (openai 3, langchain 1.5, langgraph 1.2, mcp 2.3, crewai 1.6). The brief told
    writers to inspect installed versions first; it paid off: `mcp.server.fastmcp` is gone,
    the published SQLite MCP server breaks on mcp 2.x (pinned `mcp<2` through `uvx --with`),
    and CrewAI's `LLM(model="openai/<name>")` needs LiteLLM for unknown names (use
    `provider="openai"`). -> Recorded in the lesson READMEs. -> Lesson: for fast-moving
    libraries, make "read the installed source" a step of the brief, not an afterthought.

12. **Double-counted tokens in three tool loops.** Writers recorded usage quietly on every
    response, then `show_response` recorded the final one again. Found by noticing the run
    summary was one call higher than the visible calls. -> Moved the quiet record after the
    final-reply check. -> Lesson: a summary that disagrees with what is on screen is a bug
    signal; cheap to check across every writer's output.

13. **CrewAI first-run prompt.** CrewAI asks, with a 20 s timeout, whether to upload traces
    and saves the answer in the user's data folder; telemetry env vars do not stop it.
    -> `CREWAI_TESTING=true` set before import. -> Lesson: library first-run prompts can
    leave state on the learner's machine; run lessons from a clean HOME at least once.

14. **User said stopping workers was unnecessary.** Twice I stopped running sub-agents when
    the user switched models; the user said that was not needed. -> Default now: let running
    workers finish, switch only new ones. -> Lesson: a model switch is about future spend,
    not a reason to discard in-flight work.
