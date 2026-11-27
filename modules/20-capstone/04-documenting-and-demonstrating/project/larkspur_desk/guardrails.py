"""Guardrails: cheap, deterministic checks on the way in and on the way out.

They are not the whole defence (see module 18) but they run on every request, cost no model call
and fail in a way you can test. `check_input` may rewrite the text (masking); `check_output` may
only accept or refuse.
"""

import re
from dataclasses import dataclass, field

MAX_QUESTION_CHARS = 500
INJECTION = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
    r"(reveal|show|print) (your |the )?(system )?prompt",
    r"you are now\b",
    r"developer mode",
    r"disregard (the )?(rules|instructions)",
]
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
SECRET = re.compile(r"(sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|api[_-]?key\s*[:=]\s*\S{8,}|BEGIN [A-Z ]*PRIVATE KEY)", re.I)
CITATION = re.compile(r"\[([a-z0-9-]+)\]")


@dataclass
class InputVerdict:
    ok: bool
    text: str  # the text to use from here on (masked)
    reasons: list = field(default_factory=list)


def check_input(text):
    if not text.strip():
        return InputVerdict(False, "", ["empty question"])
    if len(text) > MAX_QUESTION_CHARS:
        return InputVerdict(False, text[:60], [f"question longer than {MAX_QUESTION_CHARS} characters"])
    lowered = text.lower()
    for pattern in INJECTION:
        if re.search(pattern, lowered):
            return InputVerdict(False, text, ["looks like a prompt-injection attempt"])
    masked = EMAIL.sub("[email]", text)
    masked = PHONE.sub("[phone]", masked)
    reasons = ["masked personal data"] if masked != text else []
    return InputVerdict(True, masked, reasons)


def check_output(answer, known_ids, used_tool):
    """Return (ok, reason). An answer must cite a known source id, or come from a tool result."""
    if SECRET.search(answer):
        return False, "answer contains something shaped like a secret"
    cited = set(CITATION.findall(answer))
    if cited and not cited <= set(known_ids) | {"tickets"}:
        return False, f"answer cites unknown source(s): {sorted(cited - set(known_ids))}"
    if not cited and not used_tool:
        return False, "answer cites no source"
    if len(answer) > 1200:
        return False, "answer too long"
    return True, ""
