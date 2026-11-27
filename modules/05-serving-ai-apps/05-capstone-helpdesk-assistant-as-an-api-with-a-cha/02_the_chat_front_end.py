"""05.5/2  The chat front end wired to the service

chat_page.py (Streamlit) has no model code. It talks HTTP to helpdesk_service.py. Here that
"HTTP" stays in-process: AppTest runs the page, and the page's httpx client is FastAPI's
TestClient. We also log every request the page makes, so you see exactly what passed between
the page and the service.

Run it:   ./run 05.5/2          (Windows: run 05.5/2)
"""

import logging
from pathlib import Path

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from labkit import lesson

from helpdesk_service import app, get_llm, get_model, reset_stats, stats

logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").disabled = True

PAGE = Path(__file__).parent / "chat_page.py"


def bubbles(at):
    return [f"{m.name}: " + " ".join(x.value for x in m.markdown) for m in at.chat_message]


@lesson("05.5/2", "The chat front end wired to the service")
def main(ctx):
    app.dependency_overrides[get_llm] = lambda: ctx.client
    app.dependency_overrides[get_model] = lambda: ctx.model
    reset_stats()
    api = TestClient(app)
    requests_seen = []
    api.event_hooks["request"].append(lambda r: requests_seen.append(f"{r.method} {r.url.path}"))
    try:
        ctx.step("Start the page with the service behind it")
        at = AppTest.from_file(str(PAGE), default_timeout=60)
        at.session_state["_api"] = api
        at.run()
        ctx.note(f"Page loaded, {len(at.exception)} exceptions. Requests so far: {requests_seen}")

        ctx.step("The employee chats (two turns)")
        at.sidebar.text_input(key="employee").set_value("Priya").run()
        at.chat_input[0].set_value("My laptop can't join the office Wi-Fi. Other people are fine.").run()
        at.chat_input[0].set_value("I already restarted it. What should I try next?").run()
        if at.exception:
            ctx.show_data("The page raised", [e.value for e in at.exception])
            return
        ctx.show_data("Chat bubbles", bubbles(at))
        ctx.show_data("Requests the page made", requests_seen)

        ctx.step("The 'Triage my last message' button")
        at.sidebar.button[0].click().run()
        ctx.show_data("Result shown in the sidebar", [j.value for j in at.sidebar.json])
        ctx.show_data("Requests the page made", requests_seen)
        ctx.note("The page never saw an API key or a model name. All of that stays behind the service.")

        ctx.step("The service goes down")
        import httpx

        dead = httpx.Client(base_url="http://127.0.0.1:9", timeout=3)
        at.session_state["_api"] = dead
        at.chat_input[0].set_value("Is the printer on floor 2 working?").run()
        ctx.show_data("st.error on the page", [e.value for e in at.error])
        ctx.note(f"Exceptions: {len(at.exception)}; the unanswered turn was removed, {len(at.session_state['messages'])} messages remain.")

        ctx.step("Tokens")
        for usage in stats["usage"]:
            ctx.record_usage(usage)
        ctx.note(f"The service counted {stats['requests']} requests and {len(stats['usage'])} model calls.")
    finally:
        app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
