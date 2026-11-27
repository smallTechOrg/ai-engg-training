"""05.4/3  Streamlit or Gradio? The same chat in both

We build the SAME tiny helpdesk chat twice, run each once with the same question, and compare
what each framework made us write and what we got for free. Neither is launched: Streamlit runs
through AppTest, Gradio through a direct call of its handler.

The comparison is about shape, not speed: the honest answer to "which one?" depends on who the
user is and where the app will live.

Run it:   ./run 05.4/3          (Windows: run 05.4/3)
"""

import inspect
import logging

import gradio as gr
from streamlit.testing.v1 import AppTest

from labkit import lesson

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").disabled = True

QUESTION = "My laptop can't join the office Wi-Fi. What should I try first?"
SYSTEM = "You are the first-line IT helpdesk assistant at Larkspur Labs. Answer in at most two short sentences."


def streamlit_page():
    """The Streamlit version. Runs top to bottom on every interaction; state lives in session_state."""
    import streamlit as st

    if "messages" not in st.session_state:
        st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    if prompt := st.chat_input("Describe your IT problem"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            stream = st.session_state["_client"].chat.completions.create(
                model=st.session_state["_model"],
                messages=[{"role": "system", "content": st.session_state["_system"]}] + st.session_state.messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            def pieces():
                for chunk in stream:
                    if chunk.usage:
                        st.session_state["_usage"] = (chunk.usage.prompt_tokens, chunk.usage.completion_tokens)
                    for c in chunk.choices or []:
                        if c.delta.content:
                            yield c.delta.content
            st.session_state.messages.append({"role": "assistant", "content": st.write_stream(pieces())})


def gradio_chat(message, history, client, model, usage):
    """The Gradio version: one function. Gradio supplies message and history; yield the growing reply."""
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM}] + history + [{"role": "user", "content": message}],
        stream=True,
        stream_options={"include_usage": True},
    )
    text = ""
    for chunk in stream:
        if chunk.usage:
            usage.append(chunk.usage)
        for c in chunk.choices or []:
            if c.delta.content:
                text += c.delta.content
                yield text


@lesson("05.4/3", "Streamlit or Gradio? The same chat in both")
def main(ctx):
    ctx.step("The Streamlit version")
    ctx.note(f"Question: {QUESTION}")
    at = AppTest.from_function(streamlit_page, default_timeout=60)
    at.session_state["_client"], at.session_state["_model"] = ctx.client, ctx.model
    at.session_state["_usage"] = None
    at.session_state["_system"] = SYSTEM  # AppTest runs the function as its own script: pass values in through session_state
    at.run()
    at.chat_input[0].set_value(QUESTION).run()
    if at.exception:
        ctx.show_data("The Streamlit page raised", [e.value for e in at.exception])
        return
    ctx.show_data("Streamlit assistant bubble", at.chat_message[-1].markdown[0].value)
    if at.session_state["_usage"]:
        ctx.record_usage(dict(zip(("prompt_tokens", "completion_tokens"), at.session_state["_usage"])))
    else:
        ctx.record_usage(None)

    ctx.step("The Gradio version")
    usage = []

    def chat(message, history):
        yield from gradio_chat(message, history, ctx.client, ctx.model, usage)

    demo = gr.ChatInterface(chat, title="Larkspur Labs helpdesk")  # the whole UI is this one line
    answer = ""
    for answer in chat(QUESTION, []):
        pass
    ctx.show_data("Gradio assistant bubble", answer)
    ctx.record_usage(usage[0] if usage else None)
    ctx.note(f"Built a {type(demo).__name__}; public API endpoints: {[d['api_name'] for d in demo.config['dependencies'] if d.get('api_visibility') == 'public']}")

    ctx.step("What each one cost to write")
    ctx.show_data(
        "Lines of code (both include token bookkeeping and the model call)",
        {
            "Streamlit page function": len(inspect.getsource(streamlit_page).splitlines()),
            "Gradio handler (plus one line for gr.ChatInterface)": len(inspect.getsource(gradio_chat).splitlines()),
        },
    )

    ctx.step("Choosing between them")
    ctx.show_data(
        "Rules of thumb",
        {
            "Streamlit": "an internal tool or dashboard with several widgets, charts and pages; you want full control of the layout and a script that reads top to bottom; state is explicit (session_state)",
            "Gradio": "a model demo with typed inputs and outputs (text, image, audio); you want a shareable link and an HTTP API for free; chat is one line with ChatInterface",
            "Neither": "a product UI with accounts, branding and many users: build a real front end on the FastAPI service from 05.1 and 05.2",
        },
    )
    ctx.show_data(
        "Differences that matter",
        {
            "execution model": "Streamlit re-runs the whole script per interaction; Gradio calls only the handler wired to the event",
            "state": "Streamlit: st.session_state; Gradio: function arguments (history) and gr.State",
            "API": "Streamlit: none built in; Gradio: every handler is an HTTP endpoint with a Python client",
            "layout control": "Streamlit: columns, tabs, sidebar, dozens of elements; Gradio: Blocks rows, columns, tabs",
        },
    )


if __name__ == "__main__":
    main()
