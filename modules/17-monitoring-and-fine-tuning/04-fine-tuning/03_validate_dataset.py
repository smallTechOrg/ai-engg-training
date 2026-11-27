"""17.4/3  Validate a fine-tuning dataset before you spend money on it

A training run that fails at hour three because line 812 had a bad role is an expensive way to
find a typo. This script writes a small dataset to a temp folder, breaks some lines on purpose,
and runs the checks that a hosted fine-tuning service or your own trainer cares about:
  format (JSON, messages, roles, order, non-empty), size (token estimate), duplicates,
  train/validation leakage, personal data, and label balance.
It reports line numbers, so you can fix the file. No model call, no GPU.

Run it:   ./run 17.4/3          (Windows: run 17.4/3)
     or:  python modules/17-monitoring-and-fine-tuning/04-fine-tuning/03_validate_dataset.py
"""

import json
import re
import tempfile
from collections import Counter
from pathlib import Path

from labkit import lesson

CURATED = Path(__file__).with_name("curated_examples.json")
SYSTEM = "You are the Larkspur Labs IT helpdesk assistant. Reply in two or three sentences, in a calm and practical tone."
ROLES = {"system", "user", "assistant"}
MAX_TOKENS_PER_EXAMPLE = 4096  # a typical context limit for small tuned models
PII = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\bsk-[A-Za-z0-9_-]{10,}|\b\d{3}[ -]?\d{3}[ -]?\d{4}\b")


def est_tokens(text):
    return max(1, len(text) // 4)  # rough: about four characters per token


def validate(path, other=None):
    """Return a list of (line_number, problem). `other` is another file whose user texts must not appear here."""
    problems, seen, users = [], {}, []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            row = json.loads(line)
        except ValueError:
            problems.append((n, "not valid JSON"))
            continue
        msgs = row.get("messages") if isinstance(row, dict) else None
        if not isinstance(msgs, list) or not msgs:
            problems.append((n, "no `messages` list"))
            continue
        roles = [m.get("role") for m in msgs if isinstance(m, dict)]
        if any(r not in ROLES for r in roles) or len(roles) != len(msgs):
            problems.append((n, f"unknown role in {roles}"))
            continue
        if roles[-1] != "assistant":
            problems.append((n, "the last message must be the assistant's answer (the training target)"))
        if "user" not in roles:
            problems.append((n, "no user message"))
        if any(not isinstance(m.get("content"), str) or not m["content"].strip() for m in msgs):
            problems.append((n, "an empty or non-text content"))
            continue
        text = " ".join(m["content"] for m in msgs)
        if est_tokens(text) > MAX_TOKENS_PER_EXAMPLE:
            problems.append((n, f"about {est_tokens(text)} tokens, over the {MAX_TOKENS_PER_EXAMPLE} limit"))
        if PII.search(text):
            problems.append((n, "contains an email, phone number or key-like string"))
        user = next(m["content"] for m in msgs if m["role"] == "user")
        users.append(user)
        if user in seen:
            problems.append((n, f"duplicate of line {seen[user]}"))
        seen[user] = n
    if other is not None:
        other_users = {next((m["content"] for m in json.loads(l)["messages"] if m["role"] == "user"), None) for l in other.read_text(encoding="utf-8").splitlines()}
        for n, u in enumerate(users, start=1):
            if u in other_users:
                problems.append((n, "this ticket also appears in the other split (leakage)"))
    return problems


@lesson("17.4/3", "Validate a fine-tuning dataset")
def main(ctx):
    ctx.step("Write a clean dataset (train and validation) to a temp folder")
    rows = json.loads(CURATED.read_text(encoding="utf-8"))
    folder = Path(tempfile.mkdtemp(prefix="larkspur-ft-check-"))
    def line(r):
        return json.dumps({"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": r["ticket"]}, {"role": "assistant", "content": r["reply"]}]})
    train, val = folder / "train.jsonl", folder / "validation.jsonl"
    train.write_text("\n".join(line(r) for r in rows[:19]) + "\n", encoding="utf-8")
    val.write_text("\n".join(line(r) for r in rows[19:]) + "\n", encoding="utf-8")
    ctx.note(f"train {len(rows[:19])} lines, validation {len(rows[19:])} lines")

    ctx.step("Validate the clean files")
    for name, path, other in (("train", train, val), ("validation", val, train)):
        problems = validate(path, other)
        ctx.console.print(f"{name}: {'no problems' if not problems else problems}", markup=False)

    ctx.step("Now break the training file on purpose (5 defects)")
    lines = train.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1][:-5]  # truncated JSON
    lines[2] = json.dumps({"messages": [{"role": "user", "content": "Hi"}, {"role": "robot", "content": "Hello"}]})
    lines[3] = json.dumps({"messages": [{"role": "user", "content": "My VPN fails"}]})  # no answer to learn from
    lines[4] = lines[0]  # a duplicate
    lines[5] = json.dumps({"messages": [{"role": "user", "content": "Email me at jo@example.com about my laptop"}, {"role": "assistant", "content": "Sure, I will write to you."}]})
    lines.append(json.dumps({"messages": [{"role": "user", "content": rows[20]["ticket"]}, {"role": "assistant", "content": "Leaked from the validation split."}]}))  # leakage
    train.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ctx.step("Validate again: every defect should be found, with its line number")
    problems = validate(train, val)
    for n, p in problems:
        ctx.console.print(f"  line {n}: {p}", markup=False)
    expected = 6
    ctx.note(f"{len(problems)} problems reported ({expected} planted: 5 defects above plus the leakage line).")
    ctx.note("PASS: the validator caught what we planted." if len(problems) >= expected else "FAIL: the validator missed a planted defect.")

    ctx.step("Label balance: does one category dominate?")
    counts = Counter(r["category"] for r in rows)
    for cat, n in counts.most_common():
        ctx.console.print(f"  {cat:9} {n:>2} {'#' * n}", markup=False)
    ctx.note("A tuned model copies its data: if 80% of examples are `network`, it leans that way. Balance it, or at least know the skew.")
    total_tokens = sum(est_tokens(SYSTEM + r["ticket"] + r["reply"]) for r in rows)
    ctx.note(f"about {total_tokens} tokens across {len(rows)} examples; hosted services bill training per token per epoch, so this number times epochs is your training bill.")


if __name__ == "__main__":
    main()
