"""18.1/3  PII detection with Presidio (optional, opt-in download)

WARNING: Presidio's default engine downloads a ~380 MB spaCy model on first use.
This script only runs the Presidio part if you opt in:   LABKIT_ALLOW_DOWNLOADS=1
Otherwise it shows what would happen and runs the regex scrubber from 18.1/2 on the same text.

Run it:   ./run 18.1/3          (Windows: run 18.1/3)
Opt in:   LABKIT_ALLOW_DOWNLOADS=1 ./run 18.1/3     (Windows PowerShell: $env:LABKIT_ALLOW_DOWNLOADS=1; run 18.1/3)
Needs the `guardrails` extra only for the Presidio part (./setup.sh --extra guardrails or --all).
No model call is made.
"""

import os
import re

from labkit import lesson

SAMPLE = (
    "Hi, this is Priya Nair from Larkspur Labs. My laptop (asset LL-20931) is dead. "
    "Call me on +44 7700 900123 or write to priya.nair@larkspur.example. "
    "I live at 12 Mill Lane, Leeds."
)

PII = [
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"\+?\d[\d ()-]{7,}\d"), "[PHONE]"),
    (re.compile(r"\b[A-Z]{2,3}-?\d{5,}\b"), "[ID]"),
]


def regex_scrub(text):
    for rx, tag in PII:
        text = rx.sub(tag, text)
    return text


@lesson("18.1/3", "PII detection with Presidio (optional)")
def main(ctx):
    ctx.step("Warning before anything happens")
    print("  The default Presidio engine downloads a spaCy model (~380 MB) the first time it runs.")
    print("  It will NOT download anything unless you set LABKIT_ALLOW_DOWNLOADS=1.")
    ctx.show_data("Sample text", {"text": SAMPLE})

    ctx.step("The regex scrubber from 18.1/2 (always runs, no download)")
    ctx.show_data("Regex result", {"scrubbed": regex_scrub(SAMPLE)})
    ctx.note("Regexes catch emails, phones and ID-shaped strings. They miss the NAME and the ADDRESS: that needs an NLP model.")

    if os.environ.get("LABKIT_ALLOW_DOWNLOADS") != "1":
        ctx.step("Presidio part skipped (not opted in)")
        print("  With the opt-in it would: build an AnalyzerEngine (loads/downloads the spaCy model),")
        print("  detect PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, and anonymise them.")
        print("  To run it:  LABKIT_ALLOW_DOWNLOADS=1 ./run 18.1/3")
        print("  Windows PowerShell:  $env:LABKIT_ALLOW_DOWNLOADS=1; run 18.1/3")
        return

    ctx.step("Presidio: analyse and anonymise")
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
    except ImportError:
        print("  Presidio is not installed. Run: ./setup.sh --extra guardrails   (or ./setup.sh --all)")
        raise SystemExit(3)
    analyzer = AnalyzerEngine()  # default engine: spaCy en_core_web_lg
    results = analyzer.analyze(text=SAMPLE, language="en")
    ctx.show_data("Entities found", {f"{r.entity_type} ({r.score:.2f})": SAMPLE[r.start:r.end] for r in results})
    anonymised = AnonymizerEngine().anonymize(text=SAMPLE, analyzer_results=results)
    ctx.show_data("Anonymised", {"text": anonymised.text})
    ctx.note("Compare with the regex result. Presidio brings NLP (names, places) but is not perfect either: read what it found and what it missed or mislabelled.")


if __name__ == "__main__":
    main()
