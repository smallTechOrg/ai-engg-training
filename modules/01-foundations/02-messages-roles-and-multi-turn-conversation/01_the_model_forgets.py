"""01.2/1  The model forgets

A model keeps nothing between calls. This script proves it. It tells the model a fact, then
asks about it in a fresh call (the model cannot know). Then it asks again, this time
sending the earlier messages along with the question.

Run it:   ./run 01.2/1          (Windows: run 01.2/1)
     or:  python modules/01-foundations/02-messages-roles-and-multi-turn-conversation/01_the_model_forgets.py
Add --raw to see the HTTP request and response underneath.
"""

from labkit import lesson

FACT = "My favourite colour is teal. Reply with just the word: Noted."
QUESTION = "What is my favourite colour? Answer in one short sentence."


@lesson("01.2/1", "The model forgets")
def main(ctx):
    ctx.step("Call 1: tell the model a fact")
    first = [{"role": "user", "content": FACT}]
    ctx.show_messages(first)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=first)
    noted = ctx.show_response(response)

    ctx.step("Call 2: ask about it in a brand-new call")
    ctx.note("This request contains only the question. Nothing from call 1 is in it.")
    alone = [{"role": "user", "content": QUESTION}]
    ctx.show_messages(alone)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=alone)
    ctx.show_response(response)
    ctx.note("The model cannot know: each call starts from nothing but the messages in it.")

    ctx.step("Call 3: ask again, resending the history")
    ctx.note("Same question, but now the request carries call 1's message and the model's reply.")
    with_history = [
        {"role": "user", "content": FACT},
        {"role": "assistant", "content": noted},  # what the model said in call 1
        {"role": "user", "content": QUESTION},
    ]
    ctx.show_messages(with_history)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=with_history)
    ctx.show_response(response)
    ctx.note("'Memory' in a chat application is your code resending the conversation every time.")


if __name__ == "__main__":
    main()
