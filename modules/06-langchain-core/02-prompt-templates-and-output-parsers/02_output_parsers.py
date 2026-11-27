"""06.2/2  Output parsers: str, JSON and Pydantic

A parser is the last step of a chain. It turns the model's AIMessage into something your code can use.

  StrOutputParser       -> plain text
  JsonOutputParser      -> a dict (parsed from the text, tolerant of ```json fences)
  PydanticOutputParser  -> a validated object, plus `get_format_instructions()` to tell the model the shape

The parser works on the text, so it works on any chat endpoint. with_structured_output, by contrast, needs
JSON-schema or tool support. When the text is not valid, the parser raises OutputParserException.

Run it:   ./run 06.2/2          (Windows: run 06.2/2)
"""

from typing import Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from labkit import lesson

TICKET = "The shared printer on floor 3 shows 'offline' for everyone since lunch. We have a print deadline at 4pm."


class Ticket(BaseModel):
    """One triaged helpdesk ticket."""

    category: Literal["printer", "network", "access", "software", "other"]
    urgency: Literal["low", "medium", "high"] = Field(description="high if it blocks work today")
    summary: str = Field(description="One sentence")


@lesson("06.2/2", "Output parsers: str, JSON, Pydantic")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    ctx.step("Parsers are runnables: feed one a hand-made AIMessage")
    fenced = AIMessage('```json\n{"category": "printer", "urgency": "high", "summary": "Floor 3 printer offline."}\n```')
    ctx.show_data("StrOutputParser", StrOutputParser().invoke(fenced))
    ctx.show_data("JsonOutputParser (fence stripped)", JsonOutputParser().invoke(fenced))
    ctx.show_data("PydanticOutputParser", PydanticOutputParser(pydantic_object=Ticket).invoke(fenced).model_dump())
    for bad in [AIMessage("Sure! It is a printer problem."), AIMessage('{"category": "toaster", "urgency": "high", "summary": "x"}')]:
        try:
            PydanticOutputParser(pydantic_object=Ticket).invoke(bad)
        except OutputParserException as error:
            ctx.note(f"Rejected {bad.content[:40]!r}: {str(error).splitlines()[0][:90]}")

    ctx.step("Tell the model the shape: get_format_instructions()")
    parser = PydanticOutputParser(pydantic_object=Ticket)
    instructions = parser.get_format_instructions()
    ctx.note(f"{len(instructions)} characters of instructions, built from the class. First lines:")
    ctx.note(" | ".join(instructions.splitlines()[:3])[:200])

    ctx.step("The same triage with three different parsers")
    base = ChatPromptTemplate.from_messages(
        [
            ("system", "You triage IT tickets for Larkspur Labs. {format}"),
            ("human", "{ticket}"),
        ]
    )
    variants = {
        "str": (base.partial(format="Reply with one short sentence."), StrOutputParser()),
        "json": (base.partial(format="Reply with a JSON object with keys category, urgency, summary and nothing else."), JsonOutputParser()),
        "pydantic": (base.partial(format=instructions), parser),
    }
    for name, (prompt, out) in variants.items():
        ai = (prompt | model).invoke({"ticket": TICKET})
        ctx.record_usage(ai.usage_metadata)
        try:
            parsed = out.invoke(ai)
            shown = parsed.model_dump() if isinstance(parsed, BaseModel) else parsed
            ctx.show_data(f"{name} -> {type(parsed).__name__}", shown)
        except OutputParserException:
            ctx.note(f"{name}: the model's reply was not valid for this parser: {str(ai.content)[:80]!r}")
    ctx.note("Same model call, three result types. Pick the parser that gives the next step of your program what it needs.")


if __name__ == "__main__":
    main()
