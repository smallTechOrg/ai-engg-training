"""05.3/1  How a Streamlit page works: the re-run model

No model here. Streamlit runs your script from top to bottom every time the user does
something (a click, a typed message). Plain variables reset each time, but
`st.session_state` survives. We use Streamlit's AppTest to run a tiny page in-process,
click its button, and watch both.

Ideas:
  - the script is the UI: you do not wire up event handlers
  - st.session_state is the page's memory (the conversation will live there)
  - AppTest lets you test a page with no browser and no server

Run it:   ./run 05.3/1          (Windows: run 05.3/1)
"""

import logging

from streamlit.testing.v1 import AppTest

logging.getLogger("streamlit").setLevel(logging.ERROR)  # AppTest runs without a browser, so hide its harmless warnings
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").disabled = True

from labkit import lesson


def counter_page():
    """The page under test. It is ordinary Streamlit code (AppTest runs it as a script)."""
    import streamlit as st

    plain = 0  # a normal variable: rebuilt as 0 on every run
    if "clicks" not in st.session_state:
        st.session_state.clicks = 0  # session state: kept between runs
    if st.button("Ask for help"):
        plain += 1
        st.session_state.clicks += 1
    st.write(f"plain variable: {plain}")
    st.write(f"session_state.clicks: {st.session_state.clicks}")


@lesson("05.3/1", "How a Streamlit page works: the re-run model")
def main(ctx):
    ctx.step("Run the page once")
    at = AppTest.from_function(counter_page).run()
    ctx.show_data("Text on the page", [element.value for element in at.markdown])
    ctx.note("The script ran once, from the first line to the last. AppTest lets us read its elements.")

    ctx.step("Click the button three times")
    for n in range(1, 4):
        at.button[0].click().run()  # one click = one full re-run of counter_page
        ctx.show_data(f"After click {n}", [element.value for element in at.markdown])
    ctx.note("The plain variable shows 1 only on the run that handled the click. Every run resets it to 0, so it never reaches 2.")
    ctx.note("session_state kept counting. That is why a chat page keeps its message list there.")

    ctx.step("The chat elements you will use next")
    ctx.show_data(
        "Streamlit chat building blocks",
        {
            "st.chat_input": "the box at the bottom; returns the text once, on the run after the user presses Enter",
            "st.chat_message(role)": "a bubble for 'user' or 'assistant'; put st.markdown(...) inside it",
            "st.write_stream(generator)": "draws a generator's pieces live and returns the full text",
            "st.session_state": "the list of messages, token counts, the name the user typed",
        },
    )
    ctx.note("Why not `while True: input()`? The page is re-run, not looped, so you must save state yourself.")


if __name__ == "__main__":
    main()
