"""06.1/1  The same call, through LangChain

Lesson 01.1 made one chat call with the OpenAI SDK. Here is that call through LangChain's
`ChatOpenAI`, next to the raw SDK call, so you can see what LangChain adds:

  - messages become classes (SystemMessage, HumanMessage) instead of dicts
  - the reply is an AIMessage, with the token counts in `usage_metadata`
  - the model object is a Runnable, with the same `.invoke / .batch / .stream` methods
    as every other LangChain building block (next script)

Run it:   ./run 06.1/1          (Windows: run 06.1/1)
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from labkit import lesson

QUESTION = "In one sentence, what is a VPN?"


@lesson("06.1/1", "The same call, through LangChain")
def main(ctx):
    ctx.step("The raw SDK call (what you know from 01.1)")
    raw_messages = [
        {"role": "system", "content": "You are a concise IT helpdesk assistant."},
        {"role": "user", "content": QUESTION},
    ]
    response = ctx.client.chat.completions.create(model=ctx.model, messages=raw_messages)
    ctx.show_response(response)

    ctx.step("The same call with ChatOpenAI")
    ctx.note("ChatOpenAI takes the same three settings as the SDK client. Nothing here is tied to one provider.")
    model = ChatOpenAI(
        model=ctx.model,
        base_url=ctx.settings.base_url,
        api_key=ctx.settings.api_key,
        temperature=0,
    )
    lc_messages = [
        SystemMessage("You are a concise IT helpdesk assistant."),
        HumanMessage(QUESTION),
    ]
    ctx.show_data("Message classes", [f"{type(m).__name__}(type={m.type!r}): {m.content}" for m in lc_messages])
    ctx.note("Dicts also work: model.invoke([('system', '...'), ('human', '...')]) or a plain string.")
    message = model.invoke(lc_messages)

    ctx.step("Look inside the AIMessage")
    ctx.show_data(
        "Where things live",
        {
            "class": type(message).__name__,
            "message.content": message.content,
            "message.usage_metadata": message.usage_metadata,
            "message.response_metadata['finish_reason']": message.response_metadata.get("finish_reason"),
            "message.response_metadata['model_name']": "(your model)" if message.response_metadata.get("model_name") else None,
        },
    )
    if message.usage_metadata:
        ctx.record_usage(message.usage_metadata)
    ctx.note(f"model is a {type(model).__name__}; isinstance of Runnable: {hasattr(model, 'invoke') and hasattr(model, 'batch') and hasattr(model, 'stream')}")

    ctx.step("What LangChain did for you")
    ctx.show_data(
        "SDK vs LangChain",
        {
            "request": "same POST /chat/completions; LangChain converted the message classes to dicts",
            "reply": "response.choices[0].message.content  vs  message.content",
            "tokens": "response.usage.prompt_tokens  vs  message.usage_metadata['input_tokens']",
            "extra": "the model is now a Runnable, so it can be piped into chains (script 2)",
        },
    )


if __name__ == "__main__":
    main()
