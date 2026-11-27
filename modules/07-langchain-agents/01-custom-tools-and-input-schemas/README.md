# 07.1 · Custom tools and input schemas

**Module:** [07 · LangChain agents and tool use](../README.md) · **Time:** 45-60 minutes · **Model needs:** chat, tools · **Packages:** `langchain` extra (`uv sync --extra langchain`)

## What you will learn

- How `@tool` turns a Python function into a tool: name, description and argument schema are read from your code.
- How a pydantic `args_schema` adds argument descriptions and constraints, and rejects bad arguments before your function runs.
- How `model.bind_tools([...])`, `AIMessage.tool_calls` and `ToolMessage` express the loop you wrote by hand in lesson 02.
- What `langchain.agents.create_agent` does for you, and how to cap it.

## The idea

In module 02 you wrote the JSON schema, parsed the argument string, ran the function and
appended the result yourself. LangChain keeps the same protocol but generates the schema
from your function and gives the messages types (`HumanMessage`, `AIMessage`, `ToolMessage`).
The model still never runs anything: it only asks.

```mermaid
flowchart LR
    F["Python function + type hints / pydantic model"] -->|@tool| T["Tool: name, description, args schema"]
    T -->|bind_tools| M["Chat model"]
    M -->|AIMessage.tool_calls| L["Your loop or create_agent"]
    L -->|tool.invoke| T
    L -->|ToolMessage| M
```

## Scripts

Run all three with `./run 07.1` (Windows: `run 07.1`), or one at a time.

### 1. `01_tool_decorator_and_schema.py`: what `@tool` generates

```
./run 07.1/1
```

No model call. Prints the generated name, description and JSON schema, compares it with the
hand-written schema from lesson 02.1, adds a pydantic `args_schema`, and shows a bad call
being rejected.

**Expected output** (trimmed):

```
Step 2: The full schema a model would receive
Same name: True. Same description: True. The argument description is missing: type hints carry no prose.

Step 3: Add a pydantic args schema
  "ticket_id": { "description": "The ticket id, for example LL-2041.", "pattern": "^LL-\\d{4}$", "type": "string" }

Step 5: Bad arguments are rejected before your function runs
ValidationError: 1 validation error for LookupArgs
```

### 2. `02_bind_tools_loop.py`: the loop by hand, with LangChain types

```
./run 07.1/2
```

Binds two tools to a `ChatOpenAI` model, invokes it, reads `tool_calls`, runs each tool and
appends a `ToolMessage` with the matching `tool_call_id`. Capped at 4 rounds.

**Expected output** (trimmed):

```
Round 1 of at most 4
tokens: 94 in + 23 out = 117
AIMessage.tool_calls = [{'name': 'lookup_ticket', 'args': {'ticket_id': 'LL-2041'}, 'id': 'call_0_...', 'type': 'tool_call'}]
tool call | lookup_ticket({"ticket_id": "LL-2041"})
   result | open, owner Priya, waiting on a VPN token reset
Round 2 of at most 4
AIMessage.content = 'The status of ticket LL-2041 is **open**. It is currently assigned to **Priya** ...'
No tool calls: this is the final answer.
Run summary: 2 model call(s), 230 in + 55 out = 285 tokens, 3.7s
```

### 3. `03_helpdesk_agent.py`: a prebuilt agent over helpdesk tools

```
./run 07.1/3
```

Builds `create_agent(model, tools=[...], system_prompt=...)` over an invented ticket table,
runs it with `recursion_limit` 9, and prints every message of the run.

**Expected output** (trimmed):

```
ai asks for open_tickets_for({'owner': 'Priya'})
tool call | open_tickets_for({"owner": "Priya"})
   result | LL-2041, LL-2043
ai asks for lookup_ticket({'ticket_id': 'LL-2041'})
ai asks for lookup_ticket({'ticket_id': 'LL-2043'})
...
ai answers | Priya has two open tickets: LL-2041 and LL-2043. The highest priority ticket is LL-2041, "VPN token reset."
Run summary: 3 model call(s), 608 in + 103 out = 711 tokens, 6.0s
```

## Try this

1. In script 1, delete the docstring from `lookup_ticket` and print the description again. What does the model lose?
2. Make `ticket_id` an `Enum` or `Literal["LL-2041", "LL-2042"]` and look at the schema.
3. In script 2, change the question to "What is 17 plus 25?" and watch it pick the other tool.
4. In script 2, set `MAX_ROUNDS = 1` and see the cap message.
5. In script 3, lower `recursion_limit` to 3 and read how the run stops.
6. Add a third tool (`escalate_ticket`) to script 3 and ask for an escalation.

## If it does not work

- Run `./run doctor`. It checks the endpoint, the model and the optional extras.
- `ModuleNotFoundError: langchain`: install the extra with `uv sync --extra langchain`.
- The model answers in text and never calls a tool: it may not support tool calling. Doctor reports this.

## In the running scenario

The Larkspur Labs helpdesk assistant now has real tools, defined once as typed Python
functions, with ticket ids validated before any lookup runs.

**Next:** 07.2 · ReAct and plan-and-execute agents (planned)
