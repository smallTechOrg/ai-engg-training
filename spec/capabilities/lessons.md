# Capability: lesson runtime and format

## Runtime (`labkit.lesson`)

```python
from labkit import lesson

@lesson("01.1/1", "Hello, LLM")
def main(ctx):
    ctx.step("Build the request")
    messages = [{"role": "user", "content": "..."}]
    ctx.show_messages(messages)
    ctx.step("Call the model")
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    ctx.show_response(response)

if __name__ == "__main__":
    main()
```

- `ctx.client` is a real `openai.OpenAI`; `ctx.model` the configured model.
- `ctx.step(title)` numbered heading. `ctx.note(text)` commentary. `ctx.show_messages`,
  `ctx.show_response` (reply + tokens for the call), `ctx.show_stream(stream)` (prints
  deltas as they arrive, returns the text, records usage when the endpoint reports it),
  `ctx.show_tool_call(name, args, result)`.
- End of run: summary line — calls, input/output/total tokens, elapsed time. Endpoints
  that do not report usage show `not reported`.
- `--raw` prints each HTTP request and response body (headers, and so the key, are never
  printed) and each stream chunk.
- Each run appends to `logs/<UTC timestamp>-<lesson id>.jsonl`: steps, messages, tool calls, usage, errors.
- Errors: missing configuration, 401, 404, 429, connection and timeout errors print a
  plain-language fix and exit non-zero; `--raw` also prints the traceback.

## Lesson folder format

- `README.md`: what you will learn, the concept, a Mermaid flow diagram, one section per
  script (what it shows, how to run, expected output), "Try this" experiments, the
  running-scenario connection, minimum model capability.
- Scripts `01_*.py`... each adds one idea; the last applies it to the helpdesk scenario.
- Module `README.md`: goal, lesson list, what the module adds to the scenario, capstone.
