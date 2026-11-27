"""00.4/2  Catching a key before it is committed

The most common security incident in AI projects is an API key pasted into a file and
pushed. This script shows how secret scanners work: they run a handful of patterns over
every line. It writes a sample helpdesk-bot settings file full of INVENTED keys to a
temporary folder, scans it, and reports each hit with the key masked. It makes no model
calls.

Run it:   ./run 00.4/2          (Windows: run 00.4/2)
"""

import re
import tempfile
from pathlib import Path

from labkit import lesson
from labkit.config import mask

# Invented keys in realistic shapes. They are assembled from pieces so that this teaching
# file itself contains nothing a real scanner would flag.
FAKE_PROVIDER_KEY = "sk-" + "proj-" + "Zq4Lm9" * 7
FAKE_CLOUD_KEY = "AKIA" + "EXAMPLE7QTRN" + "W5KD"
FAKE_BEARER = "Bearer " + "eyJ" + "hbGciOiJIUzI1NiJ9" + "." + "ZmFrZS1wYXlsb2Fk" + "." + "c2lnbmF0dXJl"

SAMPLE_FILE = f'''# settings.py for the Larkspur Labs helpdesk bot (a deliberately bad example)
import os

COMPANY = "Larkspur Labs"
MODEL = "small-model"
API_KEY = "{FAKE_PROVIDER_KEY}"          # pasted in "just to test"
CLOUD_ACCESS_KEY = "{FAKE_CLOUD_KEY}"
TICKET_SYSTEM_HEADERS = {{"Authorization": "{FAKE_BEARER}"}}
password = "hunter2-larkspur"
ESCALATION_EMAIL = "it-escalations@larkspur.example"
GOOD_API_KEY = os.environ["LLM_API_KEY"]   # the right way: read it from the environment
'''

# (name, pattern). Real scanners carry hundreds of these; the idea is the same.
PATTERNS = [
    ("provider API key (sk-...)", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("cloud access key (AKIA...)", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer token", re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")),
    ("hard-coded password", re.compile(r"""(?i)\b(?:password|passwd|secret)\b\s*[=:]\s*["']([^"']{6,})["']""")),
]


def scan(path: Path) -> list[dict]:
    """Return one finding per pattern match: line number, what it looks like, masked value."""
    findings = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for name, pattern in PATTERNS:
            match = pattern.search(line)
            if match:
                secret = match.group(match.lastindex or 0)
                findings.append({"line": number, "looks like": name, "value": mask(secret)})
    return findings


@lesson("00.4/2", "Catching a key before it is committed")
def main(ctx):
    with tempfile.TemporaryDirectory() as folder:
        sample = Path(folder) / "settings.py"
        sample.write_text(SAMPLE_FILE, encoding="utf-8")

        ctx.step("A settings file someone is about to commit")
        ctx.note("Written to a temporary folder. Every key in it is invented. Values are masked below, as a scanner would.")
        for number, line in enumerate(SAMPLE_FILE.splitlines(), 1):
            shown = line
            for _, pattern in PATTERNS:
                found = pattern.search(shown)
                if found:
                    secret = found.group(found.lastindex or 0)
                    shown = shown.replace(secret, "<" + mask(secret) + ">")
            ctx.note(f"  {number:>2} | {shown}")

        ctx.step("Scan it")
        ctx.note(f"{len(PATTERNS)} patterns, each tried on every line:")
        for name, pattern in PATTERNS:
            ctx.note(f"  {name:<28} {pattern.pattern}")
        findings = scan(sample)
        ctx.show_data(f"{len(findings)} finding(s)", findings)

        ctx.step("What the scanner did not flag, and why")
        ctx.note("Line 11 reads the key from the environment: there is no secret in the file, so nothing to find.")
        ctx.note("Line 10 is an email address: sensitive perhaps, but not a credential.")
        ctx.note("A scanner only knows shapes. A key in an unusual format walks straight past it.")

    ctx.step("If a key does get committed")
    for line in (
        "1. Revoke the key at the provider NOW. This is the only step that makes you safe.",
        "2. Create a new key and put it in .env (which is ignored).",
        "3. Remove the key from the code and commit the fix.",
        "4. Do not rely on deleting the commit: clones, forks and caches may already hold it.",
    ):
        ctx.note(line)


if __name__ == "__main__":
    main()
