"""18.3/2  Validating structured model output (pydantic plus personal data)

The model is asked for a JSON ticket summary. Three layers of validation: the JSON parses, the shape
and field formats are right (pydantic), and no field carries personal data (the detector from
18.3/1, copied here). A failure triggers ONE re-ask with the reasons; after that the ticket goes to a human.

Run it:   ./run 18.3/2          (Windows: run 18.3/2)
     or:  python modules/18-guardrails/03-validators-and-detecting-personal-data/02_validated_structured_output.py
"""

import json
import re

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from labkit import lesson

# ---- personal-data detectors: regex finds candidates, a checksum or allow-list then confirms ----
ALLOW_EMAILS = {"it-desk@larkspur.example", "security@larkspur.example"}  # public mailboxes are not personal data


def luhn_ok(digits):
    total, flip = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if flip:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total, flip = total + d, not flip
    return total % 10 == 0


def iban_ok(s):
    s = s.replace(" ", "").upper()
    moved = s[4:] + s[:4]
    return int("".join(str(int(c, 36)) for c in moved)) % 97 == 1


def _card(m):
    d = re.sub(r"[ -]", "", m)
    return 13 <= len(d) <= 19 and luhn_ok(d)


DETECTORS = [  # (type, regex, confirm(match_text) -> bool)
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), lambda m: m.lower() not in ALLOW_EMAILS),
    ("PHONE", re.compile(r"(?<![\w-])\+\d{1,3}[\d ()-]{7,14}\d|(?<![\w-])0\d{3,4} ?\d{3} ?\d{3,4}(?![\w-])"), lambda m: True),
    ("CARD", re.compile(r"\b\d(?:[ -]?\d){12,18}\b"), _card),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b"), iban_ok),
    ("NI_NUMBER", re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2} ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b"), lambda m: True),
]


def detect(text):
    """Return a list of (type, start, end, text), longest-first, no overlaps."""
    found = []
    for kind, rx, confirm in DETECTORS:
        for m in rx.finditer(text):
            if confirm(m.group()):
                found.append((kind, m.start(), m.end(), m.group()))
    found.sort(key=lambda f: (f[1], -(f[2] - f[1])))
    out, last_end = [], -1
    for f in found:
        if f[1] >= last_end:
            out.append(f)
            last_end = f[2]
    return out


def redact(text):
    for kind, s, e, _ in reversed(detect(text)):
        text = text[:s] + f"[{kind}]" + text[e:]
    return text

TICKET = (
    "Ticket LL-20931 from Priya Nair (priya.nair@larkspur.example, +44 7700 900123): "
    "my laptop will not boot after the update. Please call me, I am in meeting room 4."
)

SYSTEM = (
    "You summarise helpdesk tickets for a public dashboard. Reply with ONE JSON object and nothing else: "
    '{"ticket_id": "LL-12345", "category": "network|hardware|software|access|other", "summary": "one sentence"}'
)


class PublicSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_id: str
    category: str
    summary: str

    @field_validator("ticket_id")
    @classmethod
    def _id(cls, v):
        if not re.fullmatch(r"LL-\d{5}", v):
            raise ValueError("ticket_id must look like LL-12345")
        return v

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v not in {"network", "hardware", "software", "access", "other"}:
            raise ValueError("category must be one of network|hardware|software|access|other")
        return v

    @field_validator("summary")
    @classmethod
    def _no_pii(cls, v):
        hits = [f"{k} {t!r}" for k, _, _, t in detect(v)]
        if hits:
            raise ValueError("summary contains personal data: " + ", ".join(hits))
        if len(v.split()) > 30:
            raise ValueError("summary longer than 30 words")
        return v


def check(raw):
    """Return (PublicSummary | None, [reasons])."""
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError:
        return None, ["reply is not a JSON object"]
    try:
        return PublicSummary.model_validate(data), []
    except ValidationError as err:
        return None, [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in err.errors()]


@lesson("18.3/2", "Validating structured model output")
def main(ctx):
    ctx.step("The validator on fixed strings (no model)")
    for raw in [
        '{"ticket_id": "LL-20931", "category": "hardware", "summary": "Laptop will not boot after an update."}',
        '{"ticket_id": "LL-20931", "category": "hardware", "summary": "Priya (priya.nair@larkspur.example) laptop will not boot."}',
        '{"ticket_id": "20931", "category": "pc", "summary": "ok"}',
        "not json at all",
    ]:
        obj, reasons = check(raw)
        ctx.show_data(raw[:60], {"valid": obj is not None, "reasons": reasons})

    ctx.step("Ask the model, validate, re-ask once")
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": TICKET}]
    final = None
    for attempt in (1, 2):  # hard cap: 2 calls
        r = ctx.client.chat.completions.create(model=ctx.model, messages=messages)
        ctx.record_usage(r.usage, quiet=True)
        raw = r.choices[0].message.content or ""
        obj, reasons = check(raw)
        ctx.show_data(f"attempt {attempt}", {"reply": raw[:220], "valid": obj is not None, "reasons": reasons})
        if obj:
            final = obj
            break
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "Rejected: " + "; ".join(reasons) + ". Reply again with corrected JSON only."}]
    if final:
        print("\n  Accepted:", final.model_dump())
    else:
        print("\n  Cap reached (2 attempts): this ticket goes to the human queue instead of the dashboard.")
    ctx.note("Layers: parse, shape (pydantic), content (personal data). Each layer has its own reason string to feed back.")


if __name__ == "__main__":
    main()
