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
