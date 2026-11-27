# 05.4 · A demo UI in Gradio; choosing between the two

**Module:** [05 · Serving AI apps: FastAPI, Streamlit, Gradio](../README.md) · **Time:** 45-60 minutes · **Model needs:** chat (scripts 2 and 3 also use streaming; script 2 uses JSON-schema output) · **Packages:** `apps` extra (Gradio, Streamlit)

## What you will learn

- How Gradio works. You write a plain function and name its input and output components (text boxes, buttons and so on). Gradio builds the page and an HTTP API.
- `gr.Interface` (one function), `gr.Blocks` (layout and events) and `gr.ChatInterface` (a chat around `fn(message, history)`).
- How streaming works in Gradio. A handler written as a generator yields the reply as it grows.
- How `gr.Error` turns a failure into a message in the page instead of a stack trace.
- When to pick Streamlit, when Gradio, and when neither.

## The idea

This lesson adds a second UI framework, built around a different idea. Streamlit re-runs a whole
script every time the user does something. Gradio connects events to functions: "when this button is
clicked, call `triage_handler` with these input values and put the result in these outputs." Nothing
else re-runs.

```mermaid
flowchart LR
    subgraph Browser
      I[Input components] --> B[Button or Enter]
      O[Output components]
    end
    B -->|event: click| H[Your handler function]
    H -->|model call| M[Model endpoint]
    M --> H
    H -->|return or yield values| O
    H -. raise gr.Error .-> T[Red toast in the page]
    G[Gradio] --- API[HTTP API and Python client, built for you]
    H --- API
```

Each handler is just a function with typed arguments, so Gradio can also offer it as an HTTP
endpoint. Streamlit cannot do that. This is why Gradio is popular for model demos that other people
or programs will call.

The app is in `gradio_demo.py`, a Blocks app with a triage tab and a chat tab. None of the scripts
launches it. They build it and call the handlers directly, as Gradio would. To see the real page, use
the one-line command in that file's docstring.

## Scripts

Run all three in order with `./run 05.4` (Windows: `run 05.4`), or one at a time.

### 1. `01_gradio_interface.py`: one function, one UI

```
./run 05.4/1
```

Wraps a helpdesk reply function in `gr.Interface` and looks at the components and the API endpoint
Gradio created. Then it calls the function the way the Submit button would.

**Expected output** (trimmed):

```
Step 1: Wrap the function in an Interface ──────────────────────────────────
What Gradio built
{ "type": "Interface", "input components": ["Textbox: Describe the problem"],
  "output components": ["Textbox: Assistant reply"], "public API endpoints": ["reply"] }

Step 2: Call the function as the Submit button would ───────────────────────
assistant | Please try restarting your laptop to refresh the network adapter. If that doesn't work, toggle your Wi-Fi off and on again ...
tokens: 49 in + 41 out = 90

Run summary: 1 model call(s), 49 in + 41 out = 90 tokens, 1.8s
```

### 2. `02_blocks_and_chat.py`: Blocks, ChatInterface, `gr.Error`

```
./run 05.4/2
```

Builds the two-tab app from `gradio_demo.py` and lists its public API endpoints. It calls the triage
handler with a ticket (structured output, as in 01.6) and triggers a `gr.Error`. Then it runs the chat
handler for two turns and counts how many times the streaming generator yields.

**Expected output** (trimmed):

```
Step 1: Build the Blocks app ───────────────────────────────────────────────
Public API endpoints Gradio created
[ "triage", "chat" ]
27 components and 38 event handlers exist in total;

Step 2: The Triage button: handler called with the input values ────────────
Outputs, in the order of outputs=[category, urgency, raw]
[ "hardware", "high", { "category": "hardware", "needs_human": true, "summary": "Front door badge reader non-functional following power outage", "urgency": "high" } ]

Step 3: A bad input: gr.Error ──────────────────────────────────────────────
The handler raised gr.Error('Please describe the problem in at least a sentence.'). In the page this is a red toast; the app keeps running.

Step 4: The Chat tab: a generator handler streams by yielding ──────────────
assistant (4 yields, last one is the whole reply): I'm sorry to hear you're having trouble staying connected to the VPN. ...

Run summary: 3 model call(s), 330 in + 172 out = 502 tokens, 5.6s
```

Most of the 38 handlers are `ChatInterface`'s own internal wiring. Only `triage` and `chat` are public.

### 3. `03_streamlit_or_gradio.py`: the same chat in both

```
./run 05.4/3
```

Builds the same streaming chat in Streamlit (`AppTest`) and Gradio (`ChatInterface`) and asks both the
same question. It compares how much code each took and prints rules of thumb for choosing.

**Expected output** (trimmed):

```
Step 1: The Streamlit version ──────────────────────────────────────────────
Streamlit assistant bubble
"Please restart your laptop and ensure your Wi-Fi is toggled on in the settings. If that fails, ..."
Step 2: The Gradio version ─────────────────────────────────────────────────
Built a ChatInterface; public API endpoints: ['chat']

Step 3: What each one cost to write ────────────────────────────────────────
{ "Streamlit page function": 26, "Gradio handler (plus one line for gr.ChatInterface)": 16 }

Run summary: 2 model call(s), 82 in + 96 out = 178 tokens, 3.2s
```

On this run both frameworks returned the same reply, because this gateway gives the same answer to
the same request. The models also invent network names ("Larkspur-Secure"). Without retrieval they have
no real data.

## Try this

1. Run the real page. Use the one-line command in `gradio_demo.py`'s docstring. Open the local address
   it prints, try both tabs, and click **Use via API** at the bottom of the page. Stop with Ctrl+C.
2. Add an output. Add a `gr.Textbox` for `needs_human` to the triage tab and extend `outputs=`.
   What must change in the handler's return value?
3. Call it as an API. With the app running, use `gradio_client.Client("http://127.0.0.1:7860").predict("My VPN is down", "Priya", api_name="/triage")`.
4. Break the chat history. In `chat_handler`, ignore `history`. Run script 2 and read turn two.
5. Switch frameworks. Port the triage form to Streamlit (`st.text_area`, `st.button`, `st.json`).
   Which version needed more lines? Which was easier to lay out your own way?
6. Make a decision. Here are three apps: a weekly metrics dashboard for the support team, a public image-captioning demo, and a chat for 500 employees with single sign-on. For each, pick Streamlit, Gradio or neither, and say why.

## If it does not work

Run `./run doctor`. It checks your settings and the `apps` extra. Install the extra with
`uv sync --extra apps`. Script 2's triage step needs a model with JSON-schema output. If yours does not
have it, the handler raises `gr.Error` and the script prints that message. Gradio may print a notice
about analytics. Set `GRADIO_ANALYTICS_ENABLED=False` to silence it.

## In the running scenario

The helpdesk assistant now has a second front end, built in about forty lines. It has a triage form
for agents and a chat for employees, and you can call each one as an API too. You can pick the right
tool for each audience. The capstone puts a front end on the FastAPI service from 05.1 and 05.2, which
is what you would do once the app has real users.

**Next:** 05.5 · Capstone: helpdesk assistant as an API with a chat front-end (planned)
