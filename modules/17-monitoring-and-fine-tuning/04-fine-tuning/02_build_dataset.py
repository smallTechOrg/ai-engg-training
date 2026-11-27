"""17.4/2  Build a fine-tuning dataset from run logs and curated examples

Chat fine-tuning data is a JSON-lines file. Each line is one example:
    {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}
Two sources:
  - curated_examples.json: invented tickets with ideal replies written by a person (the gold),
  - your run logs: real calls the helpdesk assistant already made (the `wire` events hold the
    request messages and the reply). Logged replies are the model's OWN output, so they are
    candidates for review, never gold by themselves.
The script filters and removes duplicates, splits the data into train and validation the same
way every time, and writes both files to a temporary folder. No model call, no GPU.

Run it:   ./run 17.4/2          (Windows: run 17.4/2)
     or:  python modules/17-monitoring-and-fine-tuning/04-fine-tuning/02_build_dataset.py
"""

import hashlib
import json
import re
import tempfile
from pathlib import Path

from labkit import lesson
from labkit.config import state_dir

SYSTEM = "You are the Larkspur Labs IT helpdesk assistant. Reply in two or three sentences, in a calm and practical tone."
CURATED = Path(__file__).with_name("curated_examples.json")
PII = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\bsk-[A-Za-z0-9_-]{10,}|\b\d{3}[ -]?\d{3}[ -]?\d{4}\b")
VALIDATION_SHARE = 5  # one in five examples goes to validation


def example(user, assistant, source):
    return {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}, {"role": "assistant", "content": assistant}], "_source": source}


def harvest(folder):
    """Candidate pairs from logs: helpdesk-style single-turn calls with a successful text reply."""
    out, seen_files = [], 0
    for path in sorted(folder.glob("*.jsonl")):
        seen_files += 1
        request = None
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("event") != "wire":
                continue
            body = e.get("body")
            if e.get("direction") == "request" and isinstance(body, dict):
                request = body.get("messages")
            elif e.get("direction") == "response" and isinstance(body, dict) and request:
                try:
                    reply = body["choices"][0]["message"].get("content")
                except (KeyError, IndexError, TypeError, AttributeError):
                    reply = None
                roles = [m.get("role") for m in request]
                if reply and roles == ["system", "user"] and "helpdesk" in request[0].get("content", "").lower() and isinstance(request[1].get("content"), str):
                    out.append(example(request[1]["content"], reply.strip(), "log"))
                request = None
    return out, seen_files


def keep(ex, seen):
    """Return (True, '') or (False, reason)."""
    user, reply = ex["messages"][1]["content"], ex["messages"][2]["content"]
    if PII.search(user) or PII.search(reply):
        return False, "looks like personal data or a key"
    if not 15 <= len(user) <= 600:
        return False, "ticket text too short or too long"
    if not 20 <= len(reply) <= 800:
        return False, "reply too short or too long"
    key = re.sub(r"\W+", " ", user.lower()).strip()
    if key in seen:
        return False, "duplicate ticket text"
    seen.add(key)
    return True, ""


def is_validation(ex):
    digest = hashlib.sha256(ex["messages"][1]["content"].encode("utf-8")).digest()
    return digest[0] % VALIDATION_SHARE == 0  # the same ticket always lands in the same split


@lesson("17.4/2", "Build a fine-tuning dataset from run logs")
def main(ctx):
    ctx.step("Load the curated gold examples")
    gold = [example(r["ticket"], r["reply"], "curated") for r in json.loads(CURATED.read_text(encoding="utf-8"))]
    ctx.note(f"{len(gold)} curated examples written by a person, one JSON object per ticket.")

    ctx.step("Harvest candidates from the run logs")
    logged, files = harvest(state_dir("logs"))
    ctx.note(f"{files} log file(s) read; {len(logged)} helpdesk-style single-turn calls found.")
    ctx.note("A model wrote these replies, not a person, so use them only after review. They stay labelled `log` so you can drop them.")

    ctx.step("Filter and de-duplicate (gold first, so it wins ties)")
    seen, kept, dropped = set(), [], {}
    for ex in gold + logged:
        ok, reason = keep(ex, seen)
        if ok:
            kept.append(ex)
        else:
            dropped[reason] = dropped.get(reason, 0) + 1
    ctx.note(f"kept {len(kept)} of {len(gold) + len(logged)}")
    for reason, n in sorted(dropped.items(), key=lambda kv: -kv[1]):
        ctx.console.print(f"  dropped {n:>3}: {reason}", markup=False)

    ctx.step("Split into train and validation, deterministically")
    train = [e for e in kept if not is_validation(e)]
    val = [e for e in kept if is_validation(e)]
    ctx.note(f"train {len(train)}, validation {len(val)}. A hash of the ticket text decides, so a rerun never moves an example across the line (which would leak validation data into training).")

    ctx.step("Write JSON-lines files to a temporary folder")
    folder = Path(tempfile.mkdtemp(prefix="larkspur-ft-"))
    ctx.note(f"folder: {folder}")
    for name, rows in (("train.jsonl", train), ("validation.jsonl", val)):
        with (folder / name).open("w", encoding="utf-8") as f:
            for ex in rows:
                f.write(json.dumps({"messages": ex["messages"]}, ensure_ascii=False) + "\n")  # _source stays out of the file
        ctx.console.print(f"{name}: {len(rows)} lines, {(folder / name).stat().st_size} bytes", markup=False)
    sample = json.loads((folder / "train.jsonl").read_text(encoding="utf-8").splitlines()[0])
    ctx.show_data("first training line (as written)", sample)
    by_source = {}
    for e in kept:
        by_source[e["_source"]] = by_source.get(e["_source"], 0) + 1
    ctx.note(f"sources kept: {by_source}")
    ctx.note("Next, check the files before paying for training (script 3). This script leaves the temp folder; the OS cleans it up.")


if __name__ == "__main__":
    main()
