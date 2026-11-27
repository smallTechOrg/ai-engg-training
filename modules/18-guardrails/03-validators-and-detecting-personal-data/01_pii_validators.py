"""18.3/1  Personal-data validators: regex finds, checksums confirm

Regexes over-match: any 16 digits "look like" a card. A good validator pairs the pattern with a
confirmation step (Luhn for cards, mod-97 for IBANs, an allow-list for public mailboxes), returns
spans (not just yes/no) and is measured on a labelled set, so false positives and misses are numbers
you can see. No model call.

Run it:   ./run 18.3/1          (Windows: run 18.3/1)
     or:  python modules/18-guardrails/03-validators-and-detecting-personal-data/01_pii_validators.py
"""

import re

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

# (text, the set of entity types a careful human would mark). All data invented.
LABELLED = [
    ("Mail me at priya.nair@larkspur.example about the laptop.", {"EMAIL"}),
    ("Write to it-desk@larkspur.example for help.", set()),  # public mailbox: allow-listed
    ("My card 4111 1111 1111 1111 was charged twice.", {"CARD"}),
    ("Order 4111 1111 1111 1112 has shipped.", set()),  # 16 digits, fails Luhn: not a card
    ("Call +44 7700 900123 after lunch.", {"PHONE"}),
    ("Ticket LL-20931 and asset 20931 are the same.", set()),
    ("Pay to GB82 WEST 1234 5698 7654 32 please.", {"IBAN"}),
    ("Reference GB00 WEST 1234 5698 7654 32 is a typo.", set()),  # fails mod-97
    ("NI number AB 12 34 56 C is on the form.", {"NI_NUMBER"}),
    ("Hi, this is Priya Nair and I live at 12 Mill Lane.", {"PERSON", "ADDRESS"}),  # regex cannot see these
]


def score(detector):
    tp = fp = fn = 0
    rows = []
    for text, expected in LABELLED:
        got = {f[0] for f in detector(text)}
        tp += len(got & expected)
        fp += len(got - expected)
        fn += len(expected - got)
        rows.append((text[:44], sorted(expected), sorted(got), "ok" if got == expected else "DIFF"))
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return rows, p, r, (tp, fp, fn)


@lesson("18.3/1", "Personal-data validators: regex finds, checksums confirm")
def main(ctx):
    ctx.step("Spans, not just yes/no")
    text = "Priya (priya.nair@larkspur.example, +44 7700 900123) paid with 4111 1111 1111 1111."
    ctx.show_data("detect()", {"spans": [f"{k} [{s}:{e}] {t}" for k, s, e, t in detect(text)]})
    ctx.show_data("redact()", {"out": redact(text)})

    ctx.step("Why a checksum matters")
    for label, s in [("valid Luhn", "4111111111111111"), ("one digit off", "4111111111111112")]:
        print(f"  {label:<14} {s}  luhn_ok={luhn_ok(s)}")
    print(f"  IBAN GB82 WEST 1234 5698 7654 32 mod97 ok = {iban_ok('GB82 WEST 1234 5698 7654 32')}")

    ctx.step("Measure it on a labelled set")
    rows, p, r, (tp, fp, fn) = score(detect)
    for t, exp, got, flag in rows:
        print(f"  {flag:<4} expect={str(exp):<24} got={str(got):<14} {t}")
    print(f"\n  true positives {tp}, false positives {fp}, misses {fn}  ->  precision {p:.2f}, recall {r:.2f}")
    ctx.note("Precision: of what we flagged, how much was right. Recall: of what was there, how much we found.")
    ctx.note("The misses are names and addresses: regexes cannot see them. That is what NLP-based tools (18.3/3) are for.")

    ctx.step("Same detector without the confirmations (naive regex only)")
    naive = lambda t: [(k, m.start(), m.end(), m.group()) for k, rx, _ in DETECTORS for m in rx.finditer(t)]
    _, p2, r2, (tp2, fp2, fn2) = score(naive)
    print(f"  naive: true positives {tp2}, false positives {fp2}, misses {fn2}  ->  precision {p2:.2f}, recall {r2:.2f}")
    ctx.note("The confirmations buy precision (fewer false alarms) at no cost in recall. A false alarm is not free: it blocks a legitimate ticket.")


if __name__ == "__main__":
    main()
