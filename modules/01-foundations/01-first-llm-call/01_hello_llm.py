"""01.1/1  Hello, LLM

The smallest useful conversation with a model: one message out, one reply back.

Run it:   ./run 01.1/1          (Windows: run 01.1/1)
     or:  python modules/01-foundations/01-first-llm-call/01_hello_llm.py
Add --raw to see the HTTP request and response underneath.
"""

from labkit import lesson


@lesson("01.1/1", "Hello, LLM")
def main(ctx):
    ctx.step("Write the message")
    ctx.note("A chat request is a list of messages. Each message has a role and some content.")
    messages = [
        {"role": "user", "content": "In one sentence, what is a large language model?"},
    ]
    ctx.show_messages(messages)

    ctx.step("Send it to the model")
    ctx.note(f"Endpoint: {ctx.settings.base_url}    Model: {ctx.model}")
    # This one call is the whole idea. Everything later in the course builds on it.
    response = ctx.client.chat.completions.create(
        model=ctx.model,
        messages=messages,
    )
    ctx.show_response(response)

    ctx.step("Look inside the response")
    ctx.note("The reply is an object. These are the parts you will use most often.")
    choice = response.choices[0]
    ctx.show_data(
        "Where things live",
        {
            "response.choices[0].message.role": choice.message.role,
            "response.choices[0].message.content": choice.message.content,
            "response.choices[0].finish_reason": choice.finish_reason,
            "response.model": response.model,
            "response.usage": response.usage,
        },
    )


if __name__ == "__main__":
    main()
