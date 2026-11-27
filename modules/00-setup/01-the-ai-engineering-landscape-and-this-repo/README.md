# 00.1 · The AI engineering landscape and this repo

**Module:** [00 · Setup and Python for AI work](../README.md) · **Time:** 45-60 minutes · **Model needs:** none

## What you will learn

- What "AI engineering" covers: the layers of work between one call to a model and a
  system that runs in production and is watched.
- Where the names you hear at work (RAG, agents, MCP, LangChain, LangGraph, CrewAI,
  guardrails) fit in those layers.
- Why this course builds each idea by hand before it shows you the framework that does it
  for you.
- How this repo is organised, and the few `./run` commands you will use every day.

## The idea

AI engineering is the work of turning a language model into a part of a software system
that people can rely on. A language model (LLM) is the program behind tools like ChatGPT:
you send it text and it writes text back. You do not build the model. Someone else runs it,
and you reach it over the internet with an HTTP request. Your job is everything around it:
what you send, what you do with the reply, what the model is allowed to touch, and how you
know it is working.

That work comes in layers. Each layer only makes sense once the one below it is solid.

```mermaid
flowchart BT
    G["Ground: Python environment, secrets, git, async"] --> C
    C["One model call: messages in, text out; prompts, streaming, structured output"] --> T
    T["Tools and agents: the model asks your code to act; a loop makes it an agent"] --> K
    K["Knowledge: embeddings, search, RAG over your documents"] --> S
    S["Serving: an API and a UI in front of it"] --> F
    F["Frameworks: LangChain, LangGraph, CrewAI"] --> P
    P["Protocols: MCP, a standard plug for tools and data"] --> O
    O["Operations: deployment, tracing, evaluation, monitoring, guardrails"]
```

Here is the vocabulary, from the bottom of the diagram to the top:

| Term | What it is, in one line |
|---|---|
| **LLM call** | One HTTP request: you send a list of messages and get one reply back. Everything else is built from this. |
| **Prompt** | The text you send. It includes the `system` message, which tells the model its job and its rules. Prompt engineering means writing that text with care. |
| **Structured output** | Asking for the reply as JSON that matches a set shape (a schema), so your code can read it, not just a person. |
| **Tools** (function calling) | You describe some functions to the model. It replies "please call `reset_password(user='aiko')`", your code runs that function and sends back the result. The model never runs anything itself. |
| **Agent** | A loop around tool calling: call the model, run the tools it asks for, send the results back, and repeat until it is done. |
| **RAG** (retrieval-augmented generation) | Find the passages in your documents that match the question, put them in the prompt, and ask the model to answer from them. The model learns nothing. You just show it the right page. |
| **MCP** (Model Context Protocol) | A standard way to offer tools and data to any AI assistant, so one ticket-system server works with many assistants. |
| **LangChain, LangGraph, CrewAI** | Frameworks. LangChain packages common patterns (prompts, chains, retrievers). LangGraph describes an app as a graph of steps that share state. CrewAI organises several agents into a team. |
| **Serving** | Putting your code behind an HTTP API (FastAPI) or a quick UI (Streamlit, Gradio) so people can use it. |
| **Deployment** | Packaging your code (in containers) and running it somewhere other than your laptop. |
| **Monitoring and evaluation** | Recording every call (tracing), scoring answer quality on a fixed set of test questions, and watching cost and speed. |
| **Guardrails** | Checks before and after the model runs: block prompt injection (text that tries to hijack the model's instructions), remove personal data, and refuse requests the assistant should not handle. |

### Why by hand first

Every framework in that table is a shortcut over the same few things: a list of messages,
a model call, a tool loop and a search step. If you have only ever used the framework, a
strange error deep inside it stops you cold. If you have built the loop yourself in thirty
lines, you know what the framework is doing and where to look.

So module 02 builds an agent in plain Python and module 04 builds RAG by hand. Only then do
modules 06-09 show LangChain and LangGraph doing the same things with less code.

### This repo

```
ai-engg-training/
  README.md          setup and everyday commands
  CURRICULUM.md      every module and lesson, with status (generated)
  curriculum.toml    the single list of modules and lessons
  .env.example       template for your settings; copy to .env
  .env               YOUR endpoint, key and model (never committed)
  pyproject.toml     what the project depends on
  uv.lock            the exact versions everyone installs
  run / run.cmd      the launcher (macOS/Linux / Windows)
  modules/
    00-setup/
      01-the-ai-engineering-landscape-and-this-repo/
        README.md      this file
        01_where_am_i.py
        02_course_map.py
    01-foundations/ ...
  src/labkit/        shared plumbing: client, printing, logs, launcher, doctor
  tests/             checks that every ready lesson still runs
  logs/              one log file per lesson run (created on first run)
```

Lessons do not depend on each other's code: each lesson folder stands on its own. The lesson
scripts call the model's library (`openai`) directly, so you read the real API. `labkit` only
handles printing, logging and friendly error messages.

### The commands

On macOS, Linux and WSL, type `./run`. On Windows, type `run` (without the `./`).

| Command | What it does |
|---|---|
| `./run` | Opens a menu: pick a module, then a lesson |
| `./run list` | Lists every lesson, its status, and whether your model can run it |
| `./run 01.1` | Runs every script of lesson 01.1, in order |
| `./run 00.1/2` | Runs only the second script of lesson 00.1 |
| `./run 01.1 --raw` | Also prints the exact HTTP requests and responses sent over the network |
| `./run doctor` | Checks your machine, settings, endpoint and what your model can do |
| `./run doctor --report` | Does the same and writes `doctor-report.txt` (no secrets) to send to your instructor |

Every script is also an ordinary Python file. You can run it with `uv run python <path>`.

## Scripts

Run both in order with `./run 00.1` (Windows: `run 00.1`), or one at a time.

### 1. `01_where_am_i.py`: the machine, the repo and the endpoint

```
./run 00.1/1
```

This script prints which Python is running, where the repo lives on your disk, which of the
important files are there, and your model settings with the key hidden. If you have set up
an endpoint, it ends with one "hello" call to prove that everything is connected. If you
have not, it stops there and tells you what to fill in. Both outcomes are fine for this
lesson.

**Expected output** (your paths, versions and reply will differ):

```
─────────────────────────────── 00.1/1  Where am I? ───────────────────────────────

Step 1: The machine and the Python running this script ────────────────────────────
Environment
{
  "operating system": "Darwin 25.5.0 (arm64)",
  "python version": "3.12.10",
  "python executable": "/path/to/ai-engg-training/.venv/bin/python"
}
The executable should live inside this repo's .venv folder. Lesson 00.2 explains why.

Step 2: The repo: what lives where ────────────────────────────────────────────────
Repo root: /path/to/ai-engg-training
  found    README.md        start here: setup and everyday commands
  found    CURRICULUM.md    the whole journey: every module and lesson, with status
  found    curriculum.toml  the list CURRICULUM.md is generated from
  found    .env             YOUR settings: endpoint, key, model (never committed)
  found    .env.example     the template .env is copied from
  found    modules          the lessons: one folder per module, one folder per lesson
  found    src/labkit       shared plumbing: client, printing, logs, launcher, doctor
  found    tests            checks that every ready lesson still runs
  found    logs             a record of every lesson run (created on first run)
'missing' is normal for .env before setup and for logs before your first run.

Step 3: The model endpoint ────────────────────────────────────────────────────────
Settings (the key is masked, never printed)
{
  "LLM_BASE_URL": "https://your-provider.example/v1",
  "LLM_MODEL": "your-model-name",
  "LLM_API_KEY": "sk-...xy (51 chars)"
}

Step 4: One hello to the model ────────────────────────────────────────────────────
This is the call the whole course is built on. Lesson 01.1 takes it apart.
Messages sent to the model
     user | Say hello to a new AI engineering student in one short sentence.
Reply from the model
assistant | Welcome to the exciting world of AI engineering, your journey starts now!
finish_reason: stop
tokens: 13 in + 18 out = 31

Run summary: 1 model call(s), 13 in + 18 out = 31 tokens, 1.6s
Log: logs/20260101T100000Z-00.1-1.jsonl
```

Without a `.env` file, Step 3 shows `(not set)` values and the script ends with
`No endpoint configured yet: ...` and a pointer to `./run doctor`. It makes no call.

### 2. `02_course_map.py`: the course as a stack

```
./run 00.1/2
```

This script reads `curriculum.toml` (the file the launcher and `CURRICULUM.md` are built
from). It prints the stack from the diagram above, the modules that teach each layer and how
many lessons are ready. It also shows what the helpdesk assistant can do after each layer.
It makes no model calls.

**Expected output** (the "ready" counts grow as more lessons are published):

```
────────────────────────────── 00.1/2  The course map ─────────────────────────────

Step 1: The stack, bottom to top ──────────────────────────────────────────────────
Each layer builds on the one before it. The course follows the same order.

GROUND: A working environment, secrets, git, async Python.
    00  Setup and Python for AI work

ONE MODEL CALL: Messages in, text out. Prompts, streaming, tokens, structured output.
    01  Foundations: talking to an LLM

TOOLS AND AGENTS: The model asks your code to do things; a loop turns that into an agent.
    02  Tools and agents by hand
...
OPERATIONS: Tracing, evaluation, containers, monitoring, guardrails, automation.
    10  Tracing, evaluation and testing
    16  Containers and deployment
    ...

Step 2: What is ready today ───────────────────────────────────────────────────────
  00  [..........] 0/5  Setup and Python for AI work
  01  [#.........] 1/7  Foundations: talking to an LLM
  02  [..........] 0/5  Tools and agents by hand
  ...
1 of 99 lessons ready across 21 modules. 'planned' lessons are outlined in CURRICULUM.md.

Step 3: The running scenario: IT helpdesk assistant ───────────────────────────────
Every lesson ends by applying its idea to the same assistant, at an invented company, Larkspur Labs.
  after One model call    it answers a single ticket in one shot
  after Tools and agents  it looks up tickets and resets passwords itself
  after Knowledge         it answers from the company knowledge base and cites it
  ...
  after Operations        it is monitored, guarded and deployed

Step 4: Where to go next ──────────────────────────────────────────────────────────
New to Python environments?  ./run 00.2
Ready for the model?         ./run 01.1
Browse everything:           ./run

Run summary: no model calls, 0.0s
Log: logs/20260101T100000Z-00.1-2.jsonl
```

## Try this

1. **Use the menu.** Run `./run` with no arguments and find this lesson by browsing. Then
   run `./run list` and look at the "Your setup" column. Which lessons can your endpoint run?
2. **Run the doctor.** `./run doctor` checks everything `01_where_am_i.py` checked. It also
   makes a real call and tests what your model supports (streaming, tools, JSON). Compare
   the two.
3. **See the wire.** Run `./run 00.1/1 --raw` with an endpoint set up. Find the URL, the
   headers (the key is hidden) and the JSON body. That is the whole API.
4. **Read a log.** Open the newest file in `logs/`. Every step and call of the run is there,
   one JSON object per line.
5. **Change the map.** In `02_course_map.py`, add a gain of your own to `HELPDESK_GAINS`
   (for example, after "Knowledge" it "answers in the employee's language") and run it again.
6. **Place a buzzword.** Pick a term you have heard at work (vector database, fine-tuning,
   function calling, LLM-as-judge) and decide which layer of the diagram it belongs to.
   Check your guess against `CURRICULUM.md`.

## If it does not work

- `./run: Permission denied` on macOS or Linux: run `chmod +x run setup.sh` once.
- `This repo is not set up yet`: run `./setup.sh` (Windows: `setup`), then try again.
- `missing  .env` in Step 2: copy `.env.example` to `.env` and fill in the three `LLM_`
  values. This lesson works without it, but module 01 does not.
- The hello call fails: run `./run doctor`. It names the problem (wrong key, wrong model
  name, endpoint unreachable) and tells you the fix. If you are still stuck,
  `./run doctor --report` writes a file you can send to your instructor. The file contains
  no secrets.

## In the running scenario

The course follows one system from start to finish: an IT helpdesk assistant at Larkspur
Labs, a company invented for this course. The course map shows what the assistant gains at
each layer. First it answers a single ticket. Then it uses tools to look tickets up. Then it
answers from the company knowledge base. By the end it is served, monitored and guarded.

Before any of that, it needs solid ground: an environment you can rebuild exactly, secrets
kept safe, clean version control and a way to handle many tickets at once. That is what the
rest of module 00 covers.

**Next:** 00.2 · Environments and dependencies: uv, venv, pip, pyenv, conda
