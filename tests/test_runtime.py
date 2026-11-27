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
