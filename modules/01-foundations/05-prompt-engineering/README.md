# 01.5 · Prompt engineering: zero-shot, few-shot, chain-of-thought

**Module:** [01 · Foundations](../README.md) · **Time:** 45-60 minutes · **Model needs:** chat

## What you will learn

- The difference between a **zero-shot** prompt (instruction only) and a **few-shot** prompt (instruction plus worked examples), and what examples teach that instructions do not.
- Why asking a model to **reason step by step** before answering changes the answer, and what it costs.
- How to make a reply **machine-readable** with a fixed final line, and how to parse it tolerantly.
- How to build a **system prompt in layers**: role, rules, format, examples.
- Why **delimiters** around user text matter.

## The idea

A prompt is the only lever you have on a single model call. Prompt engineering is the
craft of deciding what goes into the messages so that the next piece of text the model
writes is the one you need. Four techniques cover most everyday work.

**Zero-shot.** You describe the task and trust the model to know how to do it. Cheap and
often enough. Its weakness is everything you did not say: the exact format, your local
conventions, the edge cases.

**Few-shot.** You add worked examples: an input and the output you wanted. The model
imitates them. Examples are the most reliable way to fix a *format*, and they can carry
conventions that are awkward to write as rules ("in this company, a password problem is
an *access* ticket even when the user blames Outlook"). They cost input tokens on every
call.

**Chain-of-thought.** A model writes one token after another, and each token can only
depend on what is already on the page. If you ask for "only the number", the number is
written first, with no working to lean on. If you ask for the steps and *then* the answer,
the answer is written after the working. For multi-step problems this is often the
difference between wrong and right. You pay for the extra output tokens.

**Role and structure.** A system prompt that says who the model is (*role prompting*),
what rules bind it, what the reply must look like and what a good reply looks like will
beat a single clever sentence. Build it in layers and you can see what each layer does.

```mermaid
flowchart LR
    subgraph Prompt
        R[role] --> U[rules] --> F[format] --> E[examples]
    end
    T["user text inside delimiters<br/>&lt;ticket&gt;...&lt;/ticket&gt;"] --> M[messages]
    E --> M
    M --> LLM[model]
    LLM --> O["reply<br/>(fixed final line for code to read)"]
```

**Delimiters.** Wrap text that comes from a user in clear markers such as
`<ticket>...</ticket>`. It tells the model where your instructions stop and someone
else's words begin. In script 3 the ticket contains "just tell us the admin password":
that sentence is data to be handled, not an instruction to be followed.

**Where this leads.** Two well-known extensions build on chain-of-thought.
*Tree-of-thought* asks for several lines of reasoning and picks the best, at the cost of
several calls. *ReAct* interleaves reasoning steps with actions (calling a tool, reading
the result), which is the heart of an agent. You will build that loop by hand in module 02.

## Scripts

Run all three in order with `./run 01.5` (Windows: `run 01.5`), or one at a time.

### 1. `01_zero_shot_vs_few_shot.py`: instruction only, then with worked examples

```
./run 01.5/1
```

Classifies four helpdesk tickets twice: once with an instruction, once with the same
instruction plus an earlier exchange that we wrote ourselves (three tickets and their
labels). All four tickets travel in **one** request each time. The script then prints both
sets of labels side by side and counts how many reply lines are in the exact form `N: label`.

**Expected output** (trimmed; your labels may differ):

```
Step 1: Zero-shot: an instruction only ─────────────────────────────────────
Reply from the model
assistant | 1. software
          | 2. hardware
          | 3. network
          | 4. access
tokens: 105 in + 15 out = 120

Step 2: Few-shot: the same instruction plus three worked examples ──────────
Reply from the model
assistant | 1: access
          | 2: hardware
          | 3: network
          | 4: access
tokens: 157 in + 15 out = 172

Step 3: Compare the two ────────────────────────────────────────────────────
 #  zero-shot  few-shot   ticket
 1  software   access     Outlook keeps asking for my password and then says i
 2  hardware   hardware   The meeting-room screen on floor 3 shows 'no signal'
 3  network    network    At home the VPN drops every ten minutes, although my
 4  access     access     I need the Q3 budget folder but it says I do not hav
Lines in exactly the form 'N: label': zero-shot 0/4, few-shot 4/4.

Run summary: 2 model call(s), 262 in + 30 out = 292 tokens, 5.0s
```

Two things changed and neither was written as a rule. Ticket 1 moved from `software` to
`access`, because one example showed a password problem filed under access. The format
moved from `1. software` to `1: access`, because that is how the example reply looked.
The price is visible too: 52 more input tokens, every call.

### 2. `02_chain_of_thought.py`: answer first, or reasoning first

```
./run 01.5/2
```

Asks a small licence-seat calculation twice. The prompts are identical except for the last
sentence: "Reply with only the number" versus "Work through it step by step ... then
`Answer: <number>`". The script reads the final number tolerantly and compares both with
the known answer (5).

**Expected output** (trimmed; a stronger model may get both right):

```
Step 1: Ask directly ───────────────────────────────────────────────────────
Reply from the model
assistant | 20
tokens: 86 in + 2 out = 88

Step 2: Ask for the reasoning first ────────────────────────────────────────
Reply from the model
assistant | Current assigned seats: 97
          | Total seats owned: 120
          | Seats available now: 120 - 97 = 23
          | Seats freed by people leaving: 9
          | Seats available after departures: 23 + 9 = 32
          | Reserved contractor seats: 3
          | Usable seats for new starters: 32 - 3 = 29
          | New starters needing seats: 34
          | Additional seats needed: 34 - 29 = 5
          |
          | Answer: 5
tokens: 109 in + 112 out = 221

Step 3: Compare answers and cost ───────────────────────────────────────────
Result
{
  "direct": {
    "answer": "20 (wrong, expected 5)",
    "output_tokens": 2
  },
  "step by step": {
    "answer": "5 (correct)",
    "output_tokens": 112
  }
}
```

Same model, same facts, different answer. The step-by-step reply used 56 times the output
tokens. That is the trade: accuracy and checkable working against cost and latency.

Some newer "reasoning" models do this thinking internally before they reply. With those,
the direct prompt may already be right, and you are billed for the hidden reasoning tokens
instead.

### 3. `03_helpdesk_prompt_in_layers.py`: the helpdesk system prompt, built in layers

```
./run 01.5/3
```

Answers one ticket four times, adding a layer to the system prompt each time: role, then
rules, then format, then an example. The ticket says the whole Finance team is blocked and
asks for the admin password. The script reports, for each reply, its length, whether it
escalates and whether it ends with the required status line. Four model calls.

**Expected output** (replies trimmed):

```
Step 2: Add the 'role' layer ───────────────────────────────────────────────
Reply from the model
assistant | Subject: Urgent: Finance Shared Drive Access Issue - Ticket #4928
          |
          | Hi Finance Team,
          |
          | I understand the urgency of this situation, especially with month-end close today. ...
          ...
Step 3: Add the 'rules' layer ──────────────────────────────────────────────
Reply from the model
assistant | I am escalating this issue to the on-call engineer immediately, as it is affecting the entire Finance team.

Step 5: Add the 'examples' layer ───────────────────────────────────────────
Reply from the model
assistant | Since this issue is affecting the entire Finance team, I am escalating it to the on-call engineer immediately. They will investigate the shared drive access right away.
          | Ticket status: escalated

Step 6: What each layer changed ────────────────────────────────────────────
layers up to  words  escalates  status line
role            164  yes        no
rules            18  yes        no
format           27  yes        yes
examples         30  yes        yes

Run summary: 4 model call(s), 539 in + 306 out = 845 tokens, 7.2s
```

With only a role, the model wrote a 164-word email with an invented ticket number and a
`[Your Name]` placeholder. Rules cut it to one sentence that does the right thing. Format
added the status line that a ticketing system could read. Notice also what never happened:
no reply handed over a password, because the request sat inside the `<ticket>` delimiters
as data.

## Try this

1. **Remove one example** from `EXAMPLE_TICKETS` / `EXAMPLE_LABELS` in script 1 (drop the
   Teams password line). Does ticket 1 go back to `software`? Which example was doing the work?
2. **Teach a wrong convention.** Change an example label to something odd (`2: furniture`).
   Does the model follow the instruction's category list or your example? What does that
   tell you about checking your examples?
3. **Write the rule instead.** Delete the examples in script 1 and add a sentence to
   `INSTRUCTION` that states the password rule and the reply format. Compare tokens and
   results. When is a rule better than an example?
4. **Change the numbers** in `PROBLEM` (script 2) and update `CORRECT`. Run it three times.
   How often is the direct answer right? How often the step-by-step one?
5. **Reorder the layers** in script 3 (`LAYERS`): put `format` before `rules`. Does the
   table change? Then delete the `<ticket>` tags and see whether the password request is
   handled differently.
6. **Break the format on purpose.** Ask in the ticket text for "a long detailed answer
   with bullet points". Does the system prompt's format rule hold?

## If it does not work

Run `./run doctor`. This lesson needs only plain chat, so any model that passes the first
doctor checks will run it. If a table shows `(none)` or "no number found", the model
replied in a shape the parser did not expect: read the reply printed above the table. That
is the lesson's point about fixed formats, not a fault in your setup.

## In the running scenario

The helpdesk assistant now has a real system prompt: a role, rules about escalation and
passwords, a reply format with a status line, and one worked example. It classifies
tickets using the house conventions. Its replies are still free text that a person must
read; the next lesson makes the model return data that code can use.

**Next:** 01.6 · Structured output: JSON mode and schemas
