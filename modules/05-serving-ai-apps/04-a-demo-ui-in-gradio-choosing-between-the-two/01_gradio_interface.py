"""05.4/1  Gradio in one function: gr.Interface

Gradio's idea: you write a normal Python function, name its input and output components, and
Gradio builds the web page AND an HTTP API for it. We build an Interface around the helpdesk
reply function, inspect what Gradio made, then call the function the way Gradio would. We never
call `.launch()`, so no server starts and no browser opens.

Run it:   ./run 05.4/1          (Windows: run 05.4/1)
"""

import gradio as gr

from labkit import lesson


@lesson("05.4/1", "Gradio in one function: gr.Interface")
def main(ctx):
    def reply(ticket: str) -> str:
        """The function behind the UI: a ticket in, the assistant's reply out (the call from 01.1)."""
        response = ctx.client.chat.completions.create(
            model=ctx.model,
            messages=[
                {"role": "system", "content": "You are the first-line IT helpdesk assistant at Larkspur Labs. Reply in at most three short sentences with one thing to try first."},
                {"role": "user", "content": ticket},
            ],
        )
        return ctx.show_response(response)

    ctx.step("Wrap the function in an Interface")
    demo = gr.Interface(
        fn=reply,
        inputs=gr.Textbox(label="Describe the problem", lines=3),
        outputs=gr.Textbox(label="Assistant reply"),
        title="Larkspur Labs helpdesk",
        flagging_mode="never",
        api_name="reply",
    )
    ctx.note("Inputs and outputs are matched to the function's arguments and return value by position.")
    ctx.show_data(
        "What Gradio built",
        {
            "type": type(demo).__name__,
            "input components": [type(c).__name__ + ": " + str(c.label) for c in demo.input_components],
            "output components": [type(c).__name__ + ": " + str(c.label) for c in demo.output_components],
            "public API endpoints": [d["api_name"] for d in demo.config["dependencies"] if d.get("api_visibility") == "public"],
        },
    )
    ctx.note("demo.launch() would start a server on port 7860 and serve this page. We deliberately do not.")

    ctx.step("Call the function as the Submit button would")
    ticket = "My laptop won't connect to the office Wi-Fi. Other people near me are fine."
    ctx.show_data("Textbox value", ticket)
    text = reply(ticket)
    ctx.note(f"Gradio puts the returned string ({len(text)} characters) into the output Textbox.")

    ctx.step("What you get without writing any web code")
    ctx.show_data(
        "Gradio provides",
        {
            "web page": "inputs, a Submit button, an output box, a Clear button, a loading indicator",
            "HTTP API": "POST /gradio_api/call/reply, plus a Python client (gradio_client) and a 'Use via API' page",
            "sharing": "demo.launch(share=True) makes a temporary public link (only for demos, never for real data)",
        },
    )
    ctx.note("Compare 05.1: there you defined request and response models, status codes and docs yourself.")


if __name__ == "__main__":
    main()
