"""06.1/3  The helpdesk reply chain, with a structured step

Two chains built from the same pieces:

  1. reply chain:   templated system prompt (employee name, ticket) | model | StrOutputParser
  2. triage chain:  prompt | model.with_structured_output(Triage)  -> a validated Triage object

`with_structured_output` asks the model for output that matches a pydantic class. If the
endpoint does not support that, the script falls back to JSON in the prompt, parsed with
`PydanticOutputParser`. Either way the rest of your code receives a Triage object.

Run it:   ./run 06.1/3          (Windows: run 06.1/3)
"""

from typing import Literal

from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from labkit import lesson

TICKET = {
    "employee": "Priya",
    "ticket": "My laptop won't connect to the office Wi-Fi since this morning. Other people near me are fine. I have a client call in 20 minutes.",
}


class Triage(BaseModel):
    """Triage of one IT helpdesk ticket."""

    category: Literal["network", "hardware", "software", "access", "other"]
    urgency: Literal["low", "medium", "high"] = Field(description="high if it blocks work today")
    summary: str = Field(description="One sentence.")
    needs_human: bool = Field(description="True when a person must act.")


@lesson("06.1/3", "The helpdesk reply chain, with a structured step")
def main(ctx):
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)

    ctx.step("Chain 1: a templated reply")
    reply_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the first-line IT helpdesk assistant at Larkspur Labs. "
                "Reply to {employee} in at most four short sentences, addressed by name. "
                "Give one concrete thing to try first.",
            ),
            ("human", "Ticket:\n{ticket}"),
        ]
    )
    ctx.show_data("Prompt variables", list(reply_prompt.input_variables))
    ctx.show_messages([{"role": m.type, "content": m.content} for m in reply_prompt.invoke(TICKET).to_messages()])
    reply_chain = reply_prompt | model | StrOutputParser()
    reply = reply_chain.invoke(TICKET)
    ctx.show_data("reply_chain.invoke(...)", reply)

    ctx.step("Chain 2: structured output with a pydantic class")
    triage_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You triage IT helpdesk tickets for Larkspur Labs. "
                "needs_human is true when a person must visit, repair, approve or unlock something.",
            ),
            ("human", "Ticket from {employee}:\n{ticket}"),
        ]
    )
    triage = None
    try:
        structured = model.with_structured_output(Triage)
        ctx.note("model.with_structured_output(Triage) returns a new runnable whose output is a Triage object.")
        triage = (triage_prompt | structured).invoke(TICKET)
    except Exception as error:  # endpoint without json_schema/tool support, or a reply that failed validation
        ctx.note(f"with_structured_output did not work here ({type(error).__name__}). Falling back to JSON in the prompt.")
    if not isinstance(triage, Triage):
        parser = PydanticOutputParser(pydantic_object=Triage)
        fallback_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You triage IT helpdesk tickets for Larkspur Labs.\n{format_instructions}"),
                ("human", "Ticket from {employee}:\n{ticket}"),
            ]
        ).partial(format_instructions=parser.get_format_instructions())
        try:
            triage = (fallback_prompt | model | parser).invoke(TICKET)
        except Exception as error:
            ctx.note(f"The fallback also failed ({type(error).__name__}): the model's reply was not valid Triage JSON.")
            ctx.note("In a real app you would retry once or send the ticket to a person, as in lesson 01.7.")
    if isinstance(triage, Triage):
        ctx.show_data(f"Result: a {type(triage).__name__} object", triage.model_dump())

    ctx.step("Putting both chains to use")
    if isinstance(triage, Triage):
        queue = "on-site support" if triage.needs_human else "self-service reply"
        ctx.note(f"{triage.category} / {triage.urgency} -> {queue}")
    ctx.note("By hand (lessons 01.6, 01.7) this was a prompt, a JSON schema, a call and a validation. Here it is `prompt | structured`.")
    ctx.note("Token counts for these calls are not shown: the parsers drop the AIMessage that carries them. Script 1 showed where they live.")


if __name__ == "__main__":
    main()
