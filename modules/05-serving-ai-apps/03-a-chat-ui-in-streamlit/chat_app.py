"""A minimal Streamlit chat page for the Larkspur Labs helpdesk (lesson 05.3, scripts 2).

This is an ordinary Streamlit app. To run it for real, from the repo root:

    uv run streamlit run modules/05-serving-ai-apps/03-a-chat-ui-in-streamlit/chat_app.py

The lesson scripts do NOT start a server: they run this file with Streamlit's AppTest, which
executes the script top to bottom in-process, exactly as Streamlit does on every interaction.
"""

import streamlit as st

SYSTEM = (
    "You are the first-line IT helpdesk assistant at Larkspur Labs. Answer in at most three short "
    "sentences, give one concrete thing to try, and remember what the employee already told you."
)


def get_client_and_model():
    """A script may place its own client in session_state (the lesson does); otherwise read .env."""
    if "_client" in st.session_state:
        return st.session_state["_client"], st.session_state["_model"]
    from labkit import get_client, load_settings

    settings = load_settings().require()
    return get_client(settings), settings.model


def stream_reply(history):
    """Yield the reply piece by piece; st.write_stream() draws each piece as it arrives."""
    client, model = get_client_and_model()
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM}] + history,
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in stream:
        if chunk.usage:
            st.session_state.usage.append(
                {"prompt_tokens": chunk.usage.prompt_tokens, "completion_tokens": chunk.usage.completion_tokens}
            )
        for choice in chunk.choices or []:
            if choice.delta.content:
                yield choice.delta.content


st.title("Larkspur Labs helpdesk chat")

# Streamlit re-runs this whole file on every click or message. Anything that must survive
# a re-run lives in st.session_state.
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.usage = []

for message in st.session_state.messages:  # redraw the conversation so far
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Describe your IT problem"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        reply = st.write_stream(stream_reply(st.session_state.messages))
    st.session_state.messages.append({"role": "assistant", "content": reply})
