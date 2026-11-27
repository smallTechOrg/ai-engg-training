"""18.3/3  Regex versus Presidio on a labelled set (Presidio opt-in)

WARNING: Presidio's default engine downloads a ~380 MB spaCy model on first use. The Presidio part runs
only with LABKIT_ALLOW_DOWNLOADS=1. Without it the script scores the regex detector alone, explains what
it would do, and exits 0. Needs the `guardrails` extra only for the Presidio part. No model call.
(The regex detector is copied from 18.3/1 and the opt-in pattern from 18.1/3; nothing is imported.)

Run it:   ./run 18.3/3                              (safe default, no download)
Opt in:   LABKIT_ALLOW_DOWNLOADS=1 ./run 18.3/3     (Windows PowerShell: $env:LABKIT_ALLOW_DOWNLOADS=1; run 18.3/3)
"""

import os
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

# (text, {(type, exact text)}) : the answer key. All data invented.
KEY = [
    ("Hi, this is Priya Nair. Call +44 7700 900123.", {("PERSON", "Priya Nair"), ("PHONE", "+44 7700 900123")}),
    ("Please email dev.okafor@larkspur.example about the VPN.", {("EMAIL", "dev.okafor@larkspur.example")}),
    ("Card 4111 1111 1111 1111 was declined for Tomas Reyes.", {("CARD", "4111 1111 1111 1111"), ("PERSON", "Tomas Reyes")}),
    ("The printer on floor 3 is jammed again.", set()),
    ("Ana Costa in Leeds cannot log in.", {("PERSON", "Ana Costa"), ("LOCATION", "Leeds")}),
]
PRESIDIO_TYPES = {"PERSON": "PERSON", "EMAIL_ADDRESS": "EMAIL", "PHONE_NUMBER": "PHONE", "CREDIT_CARD": "CARD", "LOCATION": "LOCATION"}


def regex_entities(text):
    return {(k, t) for k, _, _, t in detect(text)}


def score(fn):
    tp = fp = fn_ = 0
    for text, key in KEY:
        got = fn(text)
        tp += len(got & key)
        fp += len(got - key)
        fn_ += len(key - got)
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn_) if tp + fn_ else 1.0
    return tp, fp, fn_, p, r


@lesson("18.3/3", "Regex versus Presidio on a labelled set")
def main(ctx):
    ctx.step("Warning before anything happens")
    print("  The default Presidio engine downloads a spaCy model (~380 MB) the first time it runs.")
    print("  It will NOT download anything unless you set LABKIT_ALLOW_DOWNLOADS=1.")

    ctx.step("Regex detector on the labelled set (always runs)")
    tp, fp, miss, p, r = score(regex_entities)
    print(f"  regex: true positives {tp}, false positives {fp}, misses {miss}  ->  precision {p:.2f}, recall {r:.2f}")
    for text, key in KEY:
        print(f"    missed: {sorted(key - regex_entities(text))}" if key - regex_entities(text) else "    (nothing missed)")

    if os.environ.get("LABKIT_ALLOW_DOWNLOADS") != "1":
        ctx.step("Presidio part skipped (not opted in)")
        print("  With the opt-in it would: build an AnalyzerEngine, analyse each text, map entity names, and score")
        print("  the same labelled set, so you can compare precision and recall side by side with the regex numbers.")
        print("  To run it:  LABKIT_ALLOW_DOWNLOADS=1 ./run 18.3/3")
        print("  Windows PowerShell:  $env:LABKIT_ALLOW_DOWNLOADS=1; run 18.3/3")
        return

    ctx.step("Presidio on the same labelled set")
    try:
        from presidio_analyzer import AnalyzerEngine
    except ImportError:
        print("  Presidio is not installed. Run: ./setup.sh --extra guardrails   (or ./setup.sh --all)")
        raise SystemExit(3)
    analyzer = AnalyzerEngine()  # default engine: spaCy en_core_web_lg

    def presidio_entities(text):
        return {(PRESIDIO_TYPES[x.entity_type], text[x.start:x.end]) for x in analyzer.analyze(text=text, language="en", score_threshold=0.4)
                if x.entity_type in PRESIDIO_TYPES}

    tp, fp, miss, p, r = score(presidio_entities)
    print(f"  presidio: true positives {tp}, false positives {fp}, misses {miss}  ->  precision {p:.2f}, recall {r:.2f}")
    for text, key in KEY:
        got = presidio_entities(text)
        print(f"    missed: {sorted(key - got)}  extra: {sorted(got - key)}")

    ctx.step("Union of both (a common production choice)")
    tp, fp, miss, p, r = score(lambda t: presidio_entities(t) | regex_entities(t))
    print(f"  union: true positives {tp}, false positives {fp}, misses {miss}  ->  precision {p:.2f}, recall {r:.2f}")
    ctx.note("Exact-text matching is strict on purpose: it makes the numbers honest and the differences visible. Tune thresholds and recognisers on YOUR data.")


if __name__ == "__main__":
    main()
