# AI engineering training

Hands-on lessons that take you from a first LLM call to agents, RAG, MCP, LangChain,
LangGraph, CrewAI and the infrastructure around them. Every lesson is a short explanation
plus small Python scripts you run and change.

- **Start anywhere.** Lessons are folders on one branch; no lesson depends on another's code.
- **Any provider.** Lessons talk to any OpenAI-compatible endpoint: a hosted model or one on your laptop.
- **One running example.** Each lesson shows an idea on its own, then applies it to an IT helpdesk assistant that grows through the course.

See the whole journey in the **[curriculum map](CURRICULUM.md)**.

## Get started

You need a terminal and an internet connection. You do **not** need Python installed.

| | macOS / Linux / WSL | Windows |
|---|---|---|
| 1. Set up | `./setup.sh` | `setup` |
| 2. Add your model settings | edit `.env` | edit `.env` |
| 3. Check | `./run doctor` | `run doctor` |
| 4. First lesson | `./run 01.1` | `run 01.1` |

In step 2, set three values in `.env` (examples for common providers are in the file):

```
LLM_BASE_URL=...   the address of an OpenAI-compatible endpoint
LLM_API_KEY=...    your key (any text for a local model)
LLM_MODEL=...      the model name
```

## Everyday commands

Type `./run` on macOS/Linux and `run` on Windows.

| Command | What it does |
|---|---|
| `run` | Menu: pick a module, then a lesson |
| `run list` | Every lesson, its status, and whether your model can run it |
| `run 01.1` | Run all scripts of lesson 01.1, in order |
| `run 01.1/2` | Run only its second script |
| `run 01.1 --raw` | Also show the HTTP requests and responses |
| `run doctor` | Check your machine, settings, endpoint and model capabilities |
| `run doctor --report` | Same, and write `doctor-report.txt` to send to your instructor |

Every script is also an ordinary Python file. With the environment active
(`source .venv/bin/activate`, or `.venv\Scripts\activate` on Windows) you can run
`python modules/01-foundations/01-first-llm-call/01_hello_llm.py` directly.

## What a lesson looks like

```
modules/01-foundations/01-first-llm-call/
  README.md                      the idea, a diagram, expected output, things to try
  01_hello_llm.py                the bare concept
  02_helpdesk_first_reply.py     the concept applied to the helpdesk assistant
```

When a script runs it prints numbered steps, the messages sent and received, token counts
for each call and a total, and saves a log under `logs/`.

## If something goes wrong

Run the doctor: `./run doctor`. It names the problem and the fix. If you are still stuck,
run `./run doctor --report` and send the file it writes (it contains no secrets).

<details>
<summary>The setup script cannot install uv on my machine</summary>

With any Python 3.11+ already installed:

```
python -m venv .venv
.venv/bin/python -m pip install -e .          # Windows: .venv\Scripts\python -m pip install -e .
./run doctor
```
</details>

## For instructors and contributors

- `curriculum.toml` is the single list of modules and lessons. After editing it, run
  `./run map` to regenerate `CURRICULUM.md` and the lesson tables in module READMEs.
- `src/labkit/` holds shared plumbing only (client, printing, logs, errors, launcher,
  doctor). Lesson code calls the model SDK directly so learners read the real API.
- `uv run pytest` runs every ready lesson against a local stub of the endpoint
  (`tests/stub_server.py`), so tests need no key. CI does this on Linux, macOS and Windows.
- Design notes live in `spec/`; the phased plan is `spec/roadmap.md`.
