"""06.2/1  Prompt templates: variables, partials and a history placeholder

Lesson 06.1 used a ChatPromptTemplate with two variables. Here we open the template up:

  - `input_variables`: what the template still needs from you
  - `.partial(...)`: fix some variables now, supply the rest later
  - `MessagesPlaceholder`: a slot that takes a whole list of messages (chat history, examples)

A prompt template is a Runnable: `invoke(dict)` returns a ChatPromptValue. You need no model to
test one, so templates are cheap to unit-test. One model call at the end shows the result in use.

Run it:   ./run 06.2/1          (Windows: run 06.2/1)
"""

from datetime import date

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from labkit import lesson


def show(ctx, label, prompt_value):
    ctx.show_data(label, [f"{type(m).__name__}: {m.content}" for m in prompt_value.to_messages()])


@lesson("06.2/1", "Prompt templates: variables, partials, placeholders")
def main(ctx):
    ctx.step("A template and what it still needs")
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are the IT helpdesk assistant at {company}. Today is {today}. Answer in at most {sentences} sentences."),
            ("human", "{question}"),
        ]
    )
    ctx.show_data("input_variables", sorted(prompt.input_variables))
    try:
        prompt.invoke({"question": "How do I reset my password?"})
    except KeyError as error:
        ctx.note(f"Missing variables fail at invoke time, before any model call: KeyError {error}")

    ctx.step("partial: fix what does not change")
    helpdesk_prompt = prompt.partial(company="Larkspur Labs", today=date.today().isoformat())
    ctx.show_data("input_variables after partial", sorted(helpdesk_prompt.input_variables))
    show(ctx, "Rendered", helpdesk_prompt.invoke({"sentences": 2, "question": "How do I reset my password?"}))
    ctx.note("A partial value can be a function, called at invoke time. .partial(today=lambda: ...) keeps dates fresh.")

    ctx.step("MessagesPlaceholder: a slot for a list of messages")
    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are the IT helpdesk assistant at Larkspur Labs. Be brief."),
            MessagesPlaceholder("history", optional=True),
            ("human", "{question}"),
        ]
    )
    ctx.show_data("input_variables", sorted(chat_prompt.input_variables))
    ctx.show_data("optional_variables", sorted(chat_prompt.optional_variables))
    show(ctx, "Without history", chat_prompt.invoke({"question": "And on my phone?"}))
    history = [HumanMessage("How do I set up the VPN on my laptop?"), AIMessage("Install the Larkspur VPN client and sign in with your work email.")]
    show(ctx, "With history", chat_prompt.invoke({"history": history, "question": "And on my phone?"}))
    ctx.note("Lesson 06.3 fills this slot automatically from a stored conversation.")

    ctx.step("Use it with a model")
    model = ChatOpenAI(model=ctx.model, base_url=ctx.settings.base_url, api_key=ctx.settings.api_key, temperature=0)
    chain = chat_prompt | model
    message = chain.invoke({"history": history, "question": "And on my phone?"})
    ctx.show_data("AIMessage content", message.content)
    ctx.record_usage(message.usage_metadata)
    ctx.note("In module 01 you built this list with f-strings and dicts. The template adds names, checks and reuse.")


if __name__ == "__main__":
    main()
