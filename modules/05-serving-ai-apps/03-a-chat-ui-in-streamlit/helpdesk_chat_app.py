"""The Larkspur Labs helpdesk chat page (lesson 05.3, script 3).

Builds on chat_app.py with a sidebar (who is asking, how formal to be), a "New conversation"
button, a running token count and an error message instead of a crash when the model fails.

Run it for real, from the repo root:

    uv run streamlit run modules/05-serving-ai-apps/03-a-chat-ui-in-streamlit/helpdesk_chat_app.py
"""

import streamlit as st

TONES = {
    "Friendly": "Be warm and plain.",
    "Formal": "Be formal and concise, no exclamation marks.",
}


def get_client_and_model():
    if "_client" in st.session_state:  # a lesson script may supply its own client
        return st.session_state["_client"], st.session_state["_model"]
    from labkit import get_client, load_settings

    settings = load_settings().require()
    return get_client(settings), settings.model


def system_prompt(employee: str, tone: str) -> str:
    return (
        "You are the first-line IT helpdesk assistant at Larkspur Labs. "
        f"You are talking to {employee or 'an employee'}; address them by first name. "
        f"{TONES[tone]} Answer in at most three short sentences with one concrete thing to try."
    )


def stream_reply(history, employee, tone):
    client, model = get_client_and_model()
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt(employee, tone)}] + history,
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in stream:
        if chunk.usage:
            st.session_state.tokens_in += chunk.usage.prompt_tokens
            st.session_state.tokens_out += chunk.usage.completion_tokens
        for choice in chunk.choices or []:
            if choice.delta.content:
                yield choice.delta.content


def new_conversation():
    st.session_state.messages = []


if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.tokens_in = 0
    st.session_state.tokens_out = 0

with st.sidebar:
    st.header("Settings")
    employee = st.text_input("Your name", value="", key="employee", placeholder="Priya")
    tone = st.radio("Tone", list(TONES), key="tone")
    st.button("New conversation", on_click=new_conversation)  # callback runs before the re-run
    token_box = st.empty()  # a placeholder: we can redraw it after the reply has streamed

def show_tokens():
    token_box.caption(f"Tokens used: {st.session_state.tokens_in} in, {st.session_state.tokens_out} out")


show_tokens()
st.title("Larkspur Labs helpdesk chat")
if not st.session_state.messages:
    st.info("Tell me what is not working and I will suggest a first step.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Describe your IT problem"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            reply = st.write_stream(stream_reply(st.session_state.messages, employee, tone))
            st.session_state.messages.append({"role": "assistant", "content": reply})
        except Exception as error:  # show a message, keep the page alive, drop the unanswered turn
            st.session_state.messages.pop()
            st.error(f"The model endpoint failed: {type(error).__name__}. Try again in a moment.")
    show_tokens()  # the sidebar was drawn before the reply streamed, so refresh it through the placeholder
