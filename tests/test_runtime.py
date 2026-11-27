"""Pieces of the shared runtime that lessons rely on."""

import textwrap

from stub_server import first_json_object, from_schema


def test_async_lessons_and_async_client(run, tmp_path):
    script = tmp_path / "async_lesson.py"
    script.write_text(
        textwrap.dedent(
            """
            import asyncio
            from labkit import lesson

            @lesson("99.9/1", "Async check")
            async def main(ctx):
                ctx.step("Three calls at once")
                ask = lambda: ctx.async_client.chat.completions.create(model=ctx.model, messages=[{"role": "user", "content": "hi"}])
                for response in await asyncio.gather(ask(), ask(), ask()):
                    ctx.record_usage(response.usage, quiet=True)

            if __name__ == "__main__":
                main()
            """
        ),
        encoding="utf-8",
    )
    result = run([str(script)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "3 model call(s), 63 in + 51 out = 114 tokens" in result.stdout


def test_stub_builds_values_from_a_schema():
    schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["network", "hardware"]},
            "urgency": {"type": "integer"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "owner": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        },
    }
    assert from_schema(schema) == {"category": "network", "urgency": 1, "tags": ["example"], "owner": "example"}


def test_stub_echoes_the_json_shape_shown_in_a_prompt():
    assert first_json_object('Reply as JSON like {"category": "network", "urgent": true} please') == {"category": "network", "urgent": True}
    assert first_json_object("no json here {not json}") is None


def test_missing_optional_package_is_explained(run, tmp_path):
    script = tmp_path / "needs_extra.py"
    script.write_text(
        "from labkit import lesson\n\n@lesson('99.9/2', 'Needs an extra')\ndef main(ctx):\n    import crewai_not_real  # noqa\n\n"
        "if __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    # an unknown module is an unexpected error...
    result = run([str(script)])
    assert result.returncode == 1 and "unexpected error" in result.stdout
    # ...a known optional one is explained with the install command
    script.write_text(script.read_text(encoding="utf-8").replace("crewai_not_real", "langchain_openai.not_a_module"), encoding="utf-8")
    result = run([str(script)])
    assert result.returncode == 3, result.stdout
    assert "optional 'langchain' packages" in result.stdout and "uv sync --extra langchain" in result.stdout


def test_embeddings_via_endpoint_and_stub_agent_loop_ends(run, tmp_path):
    script = tmp_path / "embed_and_tools.py"
    script.write_text(
        """
from labkit import lesson

@lesson("99.9/3", "Embed and tools")
def main(ctx):
    a, b, c = ctx.embed(["reset my password", "password reset please", "printer on fire"])
    dot = lambda x, y: sum(i * j for i, j in zip(x, y))
    assert dot(a, b) > dot(a, c)
    tools = [{"type": "function", "function": {"name": "lookup_ticket", "parameters": {"type": "object", "properties": {"ticket_id": {"type": "integer"}}, "required": ["ticket_id"]}}}]
    messages = [{"role": "user", "content": "status of 42?"}]
    for _ in range(3):
        r = ctx.client.chat.completions.create(model=ctx.model, messages=messages, tools=tools)
        ctx.record_usage(r.usage, quiet=True)
        m = r.choices[0].message
        if not m.tool_calls:
            break
        messages.append(m.model_dump(exclude_none=True))
        messages.append({"role": "tool", "tool_call_id": m.tool_calls[0].id, "content": "open"})
    assert not m.tool_calls and m.tool_calls is None or m.tool_calls == []
    ctx.note("ok")

if __name__ == "__main__":
    main()
""",
        encoding="utf-8",
    )
    result = run([str(script)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "3 model call(s)" in result.stdout  # 1 embeddings call + 2 chat calls: the tool loop ended
