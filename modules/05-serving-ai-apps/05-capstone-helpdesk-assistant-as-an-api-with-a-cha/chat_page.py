"""The helpdesk chat page, a front end for helpdesk_service.py (lesson 05.5).

The page contains no model code at all. It only speaks HTTP to the service:

    POST /chat/stream   for each reply (Server-Sent Events, read line by line)
    POST /triage        when the employee clicks "Triage my last message"

Where the service lives is decided by one thing: `st.session_state["_api"]`, an httpx client.
A lesson script puts FastAPI's TestClient there (in-process, no port). When you run the page for
real it builds `httpx.Client(base_url=$HELPDESK_API_URL)`, default http://127.0.0.1:8000:

    uv run uvicorn helpdesk_service:app --app-dir <this folder>          (terminal 1)
    uv run streamlit run <this folder>/chat_page.py                       (terminal 2)
"""

import json
import os

import streamlit as st


def api_client():
    if "_api" in st.session_state:
        return st.session_state["_api"]
    import httpx

    return httpx.Client(base_url=os.environ.get("HELPDESK_API_URL", "http://127.0.0.1:8000"), timeout=60)


class ApiProblem(Exception):
    """Anything the page should show as an error message instead of crashing."""


def stream_reply(history, employee):
    """Yield text pieces from the service's SSE stream; raise ApiProblem for any failure."""
    body = {"employee": employee, "messages": history}
    try:
        with api_client().stream("POST", "/chat/stream", json=body) as response:
            if response.status_code != 200:
                response.read()
                raise ApiProblem(f"The service answered {response.status_code}: {response.text[:160]}")
            event = "message"
            for line in response.iter_lines():
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    if event == "token":
                        yield data["text"]
                    elif event == "done":
                        st.session_state.usage.append(data.get("usage"))
                    elif event == "error":
                        raise ApiProblem(data["message"])
    except ApiProblem:
        raise
    except Exception as error:  # connection refused, timeout, ...
        raise ApiProblem(f"Could not reach the helpdesk service ({type(error).__name__}).") from error


def triage_last_message(employee):
    text = [m for m in st.session_state.messages if m["role"] == "user"][-1]["content"]  # the last thing the employee said
    st.session_state.ticket_no += 1
    ticket = {"ticket_id": f"LL-{st.session_state.ticket_no}", "employee": employee or "unknown", "text": text}
    try:
        response = api_client().post("/triage", json=ticket)
    except Exception as error:
        return {"error": f"Could not reach the helpdesk service ({type(error).__name__})."}
    if response.status_code != 200:
        return {"error": f"The service answered {response.status_code}: {response.text[:160]}"}
    body = response.json()
    st.session_state.usage.append(body.get("usage"))
    return body["triage"]


if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.usage = []
    st.session_state.ticket_no = 3000

with st.sidebar:
    st.header("Larkspur Labs helpdesk")
    employee = st.text_input("Your name", key="employee", placeholder="Priya")
    if st.button("Triage my last message", disabled=not st.session_state.messages):
        result = triage_last_message(employee)
        if "error" in result:
            st.error(result["error"])
        else:
            st.json(result)
    if st.button("New conversation"):
        st.session_state.messages = []
        st.rerun()

st.title("Helpdesk chat")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Describe your IT problem"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(stream_reply(st.session_state.messages, employee))
            st.session_state.messages.append({"role": "assistant", "content": reply})
        except ApiProblem as problem:
            st.session_state.messages.pop()  # drop the unanswered turn so the history stays valid
            st.error(str(problem))
