"""05.3/3  The helpdesk chat page: sidebar, reset button, errors

helpdesk_chat_app.py adds what a real page needs on top of 05.3/2:

  - a sidebar with the employee's name and a tone (widget values feed the system prompt)
  - a "New conversation" button wired with on_click
  - a running token count in the sidebar
  - an st.error message, not a crash, when the model endpoint is down

We drive it with AppTest and check each behaviour. It never launches a server.

Run it:   ./run 05.3/3          (Windows: run 05.3/3)
"""

import logging
from pathlib import Path

import openai
from streamlit.testing.v1 import AppTest

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").disabled = True

from labkit import lesson

APP = Path(__file__).parent / "helpdesk_chat_app.py"


def bubbles(at):
    return [{"role": m.name, "text": " ".join(x.value for x in m.markdown)} for m in at.chat_message]


@lesson("05.3/3", "The helpdesk chat page: sidebar, reset button, errors")
def main(ctx):
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.session_state["_client"] = ctx.client
    at.session_state["_model"] = ctx.model

    ctx.step("Fill in the sidebar, then ask")
    at.run()
    ctx.note(f"Before any message the page shows: {at.info[0].value!r}")
    at.sidebar.text_input(key="employee").set_value("Priya").run()
    at.sidebar.radio(key="tone").set_value("Formal").run()
    ctx.show_data("Sidebar widgets", {"employee": at.session_state["employee"], "tone": at.session_state["tone"]})
    at.chat_input[0].set_value("The VPN keeps dropping every few minutes.").run()
    if at.exception:
        ctx.show_data("The page raised", [e.value for e in at.exception])
        return
    ctx.show_data("Chat bubbles", bubbles(at))
    ctx.note("This run read the widget values and put them in the system prompt. No wiring code was needed.")
    ctx.note(f"Sidebar caption: {at.sidebar.caption[0].value}")
    tokens = (at.session_state["tokens_in"], at.session_state["tokens_out"])

    ctx.step("Click 'New conversation'")
    at.sidebar.button[0].click().run()
    ctx.note(f"Chat bubbles after the reset: {len(at.chat_message)}; messages in session_state: {len(at.session_state['messages'])}.")
    ctx.note(f"Token counts survive the reset: {at.sidebar.caption[0].value}")

    ctx.step("When the model endpoint is down")
    dead = openai.OpenAI(base_url="http://127.0.0.1:9/v1", api_key="not-used", max_retries=0, timeout=3)
    at.session_state["_client"] = dead
    at.chat_input[0].set_value("Is the printer on floor 2 working?").run()
    ctx.show_data("st.error messages on the page", [e.value for e in at.error])
    ctx.note(f"Exceptions raised: {len(at.exception)}; messages kept in history: {len(at.session_state['messages'])} (the unanswered turn was dropped).")

    ctx.step("Tokens")
    ctx.record_usage({"prompt_tokens": tokens[0], "completion_tokens": tokens[1]})
    if tokens == (0, 0):
        ctx.note("This provider reported no usage (the counter stays at 0 instead of guessing).")


if __name__ == "__main__":
    main()
