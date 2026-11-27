"""05.4/2  Blocks and ChatInterface for the helpdesk

Interface is one function. For a real tool you want a layout, several tabs and a chat, so Gradio
offers `gr.Blocks` (arrange components, wire events like `button.click(fn, inputs, outputs)`) and
`gr.ChatInterface` (a ready-made chat around a function `fn(message, history)`).

gradio_demo.py builds a two-tab app: a triage form and a chat. Here we build it and call its
handler functions directly, as Gradio would when the button is clicked. A handler that raises
`gr.Error` shows a red message in the page instead of a stack trace. A generator handler is
how Gradio streams: every `yield` replaces the chat bubble with the longer text.

Run it:   ./run 05.4/2          (Windows: run 05.4/2)
"""

import gradio as gr

from labkit import lesson

import gradio_demo  # the app in this lesson's folder


@lesson("05.4/2", "Blocks and ChatInterface for the helpdesk")
def main(ctx):
    gradio_demo.configure(ctx.client, ctx.model)
    gradio_demo.usage_log.clear()

    ctx.step("Build the Blocks app")
    demo = gradio_demo.build_demo()
    public = [d["api_name"] for d in demo.config["dependencies"] if d.get("api_visibility") == "public"]
    ctx.show_data("Public API endpoints Gradio created", public)
    ctx.note(f"{len(demo.config['components'])} components and {len(demo.config['dependencies'])} event handlers exist in total;")
    ctx.note("most handlers are ChatInterface's own plumbing. Yours are 'triage' (the button) and 'chat'.")

    ctx.step("The Triage button: handler called with the input values")
    ticket = "The badge reader at the front door has been dead since the power cut. Visitors are waiting outside."
    ctx.show_data("Inputs, in the order of inputs=[ticket, employee]", [ticket, "Mei"])
    category, urgency, raw = gradio_demo.triage_handler(ticket, "Mei")
    ctx.show_data("Outputs, in the order of outputs=[category, urgency, raw]", [category, urgency, raw])

    ctx.step("A bad input: gr.Error")
    try:
        gradio_demo.triage_handler("hi", "Mei")
    except gr.Error as error:
        ctx.note(f"The handler raised gr.Error({error.message!r}). In the page this is a red toast; the app keeps running.")

    ctx.step("The Chat tab: a generator handler streams by yielding")
    history = []
    for message in ["My VPN keeps dropping every few minutes.", "I already restarted the laptop. What next?"]:
        ctx.note(f"user: {message}")
        shown = None
        steps = 0
        for shown in gradio_demo.chat_handler(message, history):
            steps += 1  # each yield is the full reply so far
        ctx.note(f"assistant ({steps} yields, last one is the whole reply): {shown}")
        history += [{"role": "user", "content": message}, {"role": "assistant", "content": shown or ""}]
    ctx.note("history is a list of {'role', 'content'} dicts, the same shape as the messages list in lesson 01.2.")
    ctx.note("Gradio keeps that list in the browser session and passes it to the handler on every turn.")

    ctx.step("Tokens")
    for usage in gradio_demo.usage_log:
        ctx.record_usage({"prompt_tokens": usage[0], "completion_tokens": usage[1]})
    if not gradio_demo.usage_log:
        ctx.note("The provider reported no usage; nothing to add.")


if __name__ == "__main__":
    main()
