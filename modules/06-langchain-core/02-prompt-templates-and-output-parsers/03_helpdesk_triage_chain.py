"""06.2/3  Scenario: a triage chain that survives bad output

A reusable triage chain for the helpdesk: partial prompt, format instructions from the Pydantic class,
and a PydanticOutputParser. A reply that does not parse gets one "here is your error, try again"
round, then goes to a person. The model is called once for all tickets (`batch`).

Run it:   ./run 06.2/3          (Windows: run 06.2/3)
"""

from typing import Literal

from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from labkit import lesson

TICKETS = [
    "My laptop won't connect to the office Wi-Fi since this morning. Client call in 20 minutes.",
    "Can I get a licence for the design tool? It costs about 300 pounds a year.",
    "I locked myself out of my account after changing my password on my phone.",
]
MAX_ATTEMPTS = 2


class Triage(BaseModel):
    """Triage of one IT helpdesk ticket."""

    category: Literal["network", "hardware", "software", "access", "other"]
    urgency: Literal["low", "medium", "high"] = Field(description="high if it blocks work today")
    summary: str = Field(description="One sentence")
    needs_human: bool = Field(description="True when a person must act")


@lesson("06.2/3", "Scenario: triage chain with parser and a retry")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    parser = PydanticOutputParser(pydantic_object=Triage)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You triage IT helpdesk tickets for Larkspur Labs.\n{format_instructions}"),
            ("human", "Ticket:\n{ticket}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())
    ctx.step("The chain")
    ctx.show_data("variables still needed", sorted(prompt.input_variables))
    ask = prompt | model  # keep the AIMessage so we can count tokens, then parse separately

    ctx.step("Triage three tickets (one batched call)")
    replies = ask.batch([{"ticket": t} for t in TICKETS])
    for ai in replies:
        ctx.record_usage(ai.usage_metadata, quiet=True)
    for ticket, ai in zip(TICKETS, replies):
        result = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                result = parser.invoke(ai)
                break
            except OutputParserException as error:
                ctx.note(f"attempt {attempt}: not valid Triage JSON ({str(error).splitlines()[0][:70]})")
                if attempt == MAX_ATTEMPTS:
                    break
                fix = ask.invoke({"ticket": f"{ticket}\n\nYour previous reply was invalid: {str(error)[:200]}\nReply again with valid JSON only."})
                ctx.record_usage(fix.usage_metadata, quiet=True)
                ai = fix
        if result:
            queue = "on-site support" if result.needs_human else "self-service reply"
            ctx.show_data(ticket[:50] + "...", {**result.model_dump(), "queue": queue})
        else:
            ctx.note(f"Giving up after {MAX_ATTEMPTS} attempts: route {ticket[:40]!r} to a person (as in lesson 01.7).")
    ctx.note("Usage was recorded quietly per call; see the run summary.")


if __name__ == "__main__":
    main()
