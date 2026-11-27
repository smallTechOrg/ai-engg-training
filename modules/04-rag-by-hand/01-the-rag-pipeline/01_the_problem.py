"""04.1/1  The problem: a model that has never read your documents

Ask a company-specific question with no context. The model cannot know Larkspur Labs'
policy, so it guesses or deflects. That gap is what RAG fills.

Run it:   ./run 04.1/1          (Windows: run 04.1/1)
     or:  python modules/04-rag-by-hand/01-the-rag-pipeline/01_the_problem.py
Needs a chat model. Does not need the `rag` extra.
"""

from labkit import lesson

QUESTION = "How often does Larkspur Labs replace employee laptops, and who do I contact if mine breaks early?"


@lesson("04.1/1", "The problem: no context")
def main(ctx):
    ctx.step("Ask a company-specific question with no context")
    ctx.note("The policy lives in a file the model has never seen. Training data cannot contain it.")
    messages = [
        {"role": "system", "content": "You are the IT helpdesk assistant at Larkspur Labs."},
        {"role": "user", "content": QUESTION},
    ]
    ctx.show_messages(messages)
    response = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
    ctx.show_response(response)

    ctx.step("What went wrong")
    ctx.note("Whatever the reply says, nothing in the request contained the real policy.")
    ctx.note("A confident-sounding figure is a guess; a polite deflection is useless to the employee.")
    ctx.note("Fix: look the answer up in your own documents and put it in the prompt. Next script.")


if __name__ == "__main__":
    main()
