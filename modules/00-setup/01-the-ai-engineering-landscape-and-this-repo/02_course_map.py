"""00.1/2  The course map

Reads curriculum.toml (the same file the launcher and CURRICULUM.md use) and prints the
course as layers: each layer of the AI engineering stack, the modules that teach it, and
how many of their lessons are ready. It ends with what the running scenario, the IT
helpdesk assistant, gains at each layer. No model calls.

Run it:   ./run 00.1/2          (Windows: run 00.1/2)
"""

from labkit import lesson
from labkit.catalog import load_catalog, scenario

# The stack, bottom to top. Each layer only makes sense once the one below is understood.
LAYERS = [
    ("Ground", ["00"], "A working environment, secrets, git, async Python."),
    ("One model call", ["01"], "Messages in, text out. Prompts, streaming, tokens, structured output."),
    ("Tools and agents", ["02"], "The model asks your code to do things; a loop turns that into an agent."),
    ("Knowledge", ["03", "04"], "Embeddings and search, then RAG: answers grounded in your documents."),
    ("Serving", ["05"], "Put the model behind an API and a simple UI."),
    ("Frameworks", ["06", "07", "08", "09"], "LangChain and LangGraph: the same ideas with less code to write."),
    ("Protocols", ["11", "12"], "MCP: a standard plug between models and tools or data."),
    ("Advanced agents", ["13", "14", "15"], "Reflection, planning, memory, multi-agent crews, agentic RAG."),
    ("Operations", ["10", "16", "17", "18", "19"], "Tracing, evaluation, containers, monitoring, guardrails, automation."),
    ("Capstone", ["20"], "Design, build, deploy and present a complete system."),
]

# What the helpdesk assistant can do once each layer is in place.
HELPDESK_GAINS = [
    ("One model call", "answers a single ticket in one shot"),
    ("Tools and agents", "looks up tickets and resets passwords itself"),
    ("Knowledge", "answers from the company knowledge base and cites it"),
    ("Serving", "is reachable from a chat window"),
    ("Frameworks", "routes tickets to specialists and waits for approvals"),
    ("Protocols", "shares its ticket and asset tools with any MCP client"),
    ("Advanced agents", "learns from resolved tickets; works as a team of agents"),
    ("Operations", "is monitored, guarded and deployed"),
]


def bar(ready: int, total: int, width: int = 10) -> str:
    """A plain-text progress bar, e.g. [###.......] 3/10."""
    filled = round(width * ready / total) if total else 0
    return "[" + "#" * filled + "." * (width - filled) + f"] {ready}/{total}"


@lesson("00.1/2", "The course map")
def main(ctx):
    modules = {module.id: module for module in load_catalog()}

    ctx.step("The stack, bottom to top")
    ctx.note("Each layer builds on the one before it. The course follows the same order.")
    for name, module_ids, summary in LAYERS:
        ctx.note("")
        ctx.note(f"{name.upper()}: {summary}")
        for module_id in module_ids:
            module = modules.get(module_id)
            if module is None:
                continue
            ctx.note(f"    {module.id}  {module.title}")

    ctx.step("What is ready today")
    total_ready = total = 0
    for module in modules.values():
        ready = module.count("ready")
        total_ready += ready
        total += len(module.lessons)
        ctx.note(f"  {module.id}  {bar(ready, len(module.lessons))}  {module.title}")
    ctx.note("")
    ctx.note(f"{total_ready} of {total} lessons ready across {len(modules)} modules. 'planned' lessons are outlined in CURRICULUM.md.")

    ctx.step(f"The running scenario: {scenario() or 'IT helpdesk assistant'}")
    ctx.note("Every lesson ends by applying its idea to the same assistant, at an invented company, Larkspur Labs.")
    for layer, gain in HELPDESK_GAINS:
        ctx.note(f"  after {layer:<17} it {gain}")

    ctx.step("Where to go next")
    ctx.note("New to Python environments?  ./run 00.2")
    ctx.note("Ready for the model?         ./run 01.1")
    ctx.note("Browse everything:           ./run")


if __name__ == "__main__":
    main()
