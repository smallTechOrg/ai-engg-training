# 01.1 · Your first LLM call

**Module:** [01 · Foundations](../README.md) · **Time:** 45-60 minutes · **Model needs:** chat, streaming

## What you will learn

- A model call is one request: a list of **messages** goes out, one **reply** comes back.
- What the reply object contains, and where the text, the stop reason and the token counts live.
- How a **system message** turns a general model into an assistant with a job.
- What **streaming** is and why chat interfaces use it.

## The idea

A large language model is a program that continues text. A *chat* model wraps that in a
simple contract: you send a list of messages, each with a **role** (`system`, `user`,
`assistant`) and some **content**; the model writes the next `assistant` message.

The model remembers nothing between calls. Everything it knows about your conversation is
in the messages you send *this time*. That single fact explains most of what comes later:
memory, context windows, RAG and agents are all ways of deciding what to put in that list.

```mermaid
sequenceDiagram
    participant You as Your script
    participant API as Model endpoint (LLM_BASE_URL)
    You->>API: POST /chat/completions (model, messages)
    API-->>You: choices[0].message (role: assistant, content) + usage
```

Nearly every provider accepts this same request shape, which is why this course needs only
three settings (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`) to work with any of them.

## Scripts

Run both in order with `./run 01.1` (Windows: `run 01.1`), or one at a time.

### 1. `01_hello_llm.py`: one message out, one reply back

```
./run 01.1/1
```

Builds a one-message conversation, sends it, prints the reply, then opens up the response
object to show where each part lives.

**Expected output** (the wording of the reply and the token numbers will differ):

```
──────────────────────────── 01.1/1  Hello, LLM ────────────────────────────

Step 1: Write the message ──────────────────────────────────────────────────
A chat request is a list of messages. Each message has a role and some content.
Messages sent to the model
     user | In one sentence, what is a large language model?

Step 2: Send it to the model ───────────────────────────────────────────────
Reply from the model
assistant | A large language model is a neural network trained on vast amounts of text...
finish_reason: stop
tokens: 18 in + 27 out = 45

Step 3: Look inside the response ───────────────────────────────────────────
Where things live
{
  "response.choices[0].message.role": "assistant",
  "response.choices[0].message.content": "A large language model is ...",
  "response.choices[0].finish_reason": "stop",
  ...
}

Run summary: 1 model call(s), 18 in + 27 out = 45 tokens, 1.4s
Log: logs/20260101T100000Z-01.1-1.jsonl
```

Read the code: the only line that talks to the model is
`ctx.client.chat.completions.create(model=..., messages=...)`. `ctx.client` is a standard
`openai.OpenAI` client; the `ctx.step` / `ctx.show_*` calls only print.

### 2. `02_helpdesk_first_reply.py`: the helpdesk assistant's first reply

```
./run 01.1/2
```

The same call applied to this course's running scenario, an IT helpdesk assistant. A
`system` message gives the model its job and its rules, the `user` message is a support
ticket, and the reply is **streamed**.

**Expected output:** the two messages are printed, then the reply appears a few words at a
time rather than all at once, followed by the token counts:

```
Step 2: Ask for the reply as a stream ──────────────────────────────────────
Reply from the model (streaming)
assistant | Hi Priya, sorry about the timing. First, turn Wi-Fi off and on again...
tokens: 96 in + 58 out = 154
```

If you see `tokens: not reported by this endpoint`, your provider does not send usage for
streamed replies. The lesson still works.

```mermaid
flowchart LR
    S[system: you are the helpdesk assistant] --> M[messages]
    T[user: ticket #4821] --> M
    M --> LLM[model]
    LLM -- piece by piece --> R[reply to the employee]
```

## Try this

1. **See the wire.** Run `./run 01.1/1 --raw`. Find the request body. Is there anything in it
   besides the model name and the messages? This is the entire API.
2. **Change the question** in `01_hello_llm.py` to ask for "three bullet points". Watch
   `completion_tokens` change. You pay for both directions.
3. **Remove the system message** from `02_helpdesk_first_reply.py` and run it again. How does
   the tone and length of the reply change? What did the system message buy you?
4. **Break a rule on purpose.** Add "Reply only in formal legal English" to the system
   prompt. Which instruction wins when rules conflict?
5. **Run script 1 twice.** Is the reply word-for-word identical? Keep your answer in mind
   for lesson 01.3 (sampling parameters).
6. **Open the log file** named at the end of a run. Everything the script sent and received
   is recorded there.

## If it does not work

Run `./run doctor`. It checks your settings and makes a real call, and tells you exactly
what to fix. Lesson scripts explain the common failures too (wrong key, wrong model name,
endpoint unreachable) instead of printing a stack trace.

## In the running scenario

The helpdesk assistant can now answer a single ticket in one shot. It has no memory of
earlier messages, cannot look anything up and cannot take any action. The rest of module
01 improves what one call can do; module 02 gives it tools.

**Next:** 01.2 · Messages, roles and multi-turn conversation
