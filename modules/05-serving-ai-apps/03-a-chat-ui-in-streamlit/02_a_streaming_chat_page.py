"""05.3/2  A streaming chat page, tested with AppTest

chat_app.py is a complete Streamlit chat page: it keeps the conversation in session_state,
redraws it on every run, and streams each reply with st.write_stream (the streaming call
from 01.3, wrapped in a generator). This script drives it like a user would, with no browser
and no server: type a message, run, read the chat bubbles, type another.

The page uses a client we place in session_state, so the model calls go through the course's
client. The page records token usage in session_state; we add it to this run's totals.

Run it:   ./run 05.3/2          (Windows: run 05.3/2)
"""

import logging
from pathlib import Path

from streamlit.testing.v1 import AppTest

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").disabled = True

from labkit import lesson

APP = Path(__file__).parent / "chat_app.py"


def bubbles(at):
    return [{"role": m.name, "text": " ".join(x.value for x in m.markdown)} for m in at.chat_message]


@lesson("05.3/2", "A streaming chat page, tested with AppTest")
def main(ctx):
    ctx.step("Load the page and hand it the lesson's client")
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["_client"] = ctx.client
    at.session_state["_model"] = ctx.model
    at.run()
    ctx.note(f"Page title: {at.title[0].value!r}. Chat bubbles so far: {len(at.chat_message)} (the conversation is empty).")
    ctx.note(f"Exceptions raised by the page: {len(at.exception)}")

    ctx.step("Turn 1: the employee types a message")
    at.chat_input[0].set_value("My laptop can't join the office Wi-Fi. Other people are fine.").run()
    if at.exception:
        ctx.show_data("The page raised", [e.value for e in at.exception])
        return
    ctx.show_data("Chat bubbles", bubbles(at))
    ctx.note("st.write_stream consumed the generator; the full reply was saved to session_state.messages.")

    ctx.step("Turn 2: a follow-up that only makes sense with memory")
    at.chat_input[0].set_value("I already restarted it. What should I try next?").run()
    ctx.show_data("Chat bubbles", bubbles(at))
    ctx.note(f"The page sent {len(at.session_state['messages'])} messages to the model on this turn: the whole history, as in lesson 01.2.")

    ctx.step("Tokens")
    for usage in at.session_state["usage"]:
        ctx.record_usage(usage)  # the page recorded each streamed call's usage; add them to our totals
    if not at.session_state["usage"]:
        ctx.note("The provider sent no usage chunks, so the page has nothing to report.")
    ctx.note("The history is re-sent every turn, so the prompt tokens grow with the conversation.")


if __name__ == "__main__":
    main()
