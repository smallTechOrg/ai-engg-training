"""20.3/1  Two static audits: a Dockerfile lint and a secret scan

Docker is not required (or used) here: both audits only read files. They run on the reference
project in `project/` (which must pass) and on `samples/` (which contains deliberate mistakes and
invented secrets, so you can see what a finding looks like).

  Dockerfile lint   pinned base tag, non-root user, no secrets in ENV/ARG, a HEALTHCHECK,
                    no remote ADD, exec-form CMD, dependency layer before the source, pip without cache.
  Secret scan       key-shaped strings, private keys, credentials inside URLs, password = "..." lines.

Findings never print the secret itself, only its first four characters. This is a safety net, not a
replacement for a real scanner in CI (gitleaks, trufflehog): add one and keep this as a unit test.

Run it:   ./run 20.3/1          (Windows: run 20.3/1)
"""

import re
import sys
from pathlib import Path

from labkit import lesson

HERE = Path(__file__).parent
SECRET_NAME = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|PASSWD)", re.I)
SECRET_PATTERNS = [
    ("api key (sk-...)", re.compile(r"sk-[A-Za-z0-9]{16,}")),
    ("cloud access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key block", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("credentials in a URL", re.compile(r"[a-z]+://[^/\s:@]+:[^/\s:@]{6,}@")),
    ("assigned secret", re.compile(r"""(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*["']([^"'\s]{8,})["']""")),
]
SKIP_DIRS = {"__pycache__", ".git", "logs", ".venv", "kb"}


def lint_dockerfile(text):
    """Return a list of (rule, message). Empty list means clean."""
    findings = []
    lines = [line.strip() for line in text.replace("\\\n", " ").splitlines() if line.strip() and not line.strip().startswith("#")]
    froms = [line.split()[1] for line in lines if line.upper().startswith("FROM ")]
    for image in froms:
        if image.lower() != "scratch" and (":" not in image or image.endswith(":latest")):
            findings.append(("pin-base-image", f"base image '{image}' is not pinned to a version tag"))
    user = [i for i, line in enumerate(lines) if line.upper().startswith("USER ")]
    if not user or lines[user[-1]].split()[1] in ("root", "0"):
        findings.append(("non-root", "the container runs as root: add a USER before CMD"))
    for line in lines:
        if line.upper().startswith(("ENV ", "ARG ")):
            for name_value in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=(\S+)", line):
                if SECRET_NAME.search(name_value[0]) and name_value[1]:
                    findings.append(("no-secrets", f"{name_value[0]} is set in the image; supply it at run time"))
        if re.match(r"ADD\s+https?://", line, re.I):
            findings.append(("no-remote-add", "ADD from a URL is unverified: download and check a checksum, or avoid it"))
        if "pip install" in line and "--no-cache-dir" not in line:
            findings.append(("pip-cache", "pip install without --no-cache-dir bloats the image"))
    if not any(line.upper().startswith("HEALTHCHECK") for line in lines):
        findings.append(("healthcheck", "no HEALTHCHECK: the platform cannot tell a hung container from a healthy one"))
    cmds = [line for line in lines if line.upper().startswith(("CMD ", "ENTRYPOINT "))]
    if cmds and not cmds[-1].split(None, 1)[1].startswith("["):
        findings.append(("exec-form", "CMD in shell form: signals (docker stop) will not reach the process"))
    copies = [i for i, line in enumerate(lines) if line.upper().startswith("COPY ")]
    installs = [i for i, line in enumerate(lines) if "pip install" in line]
    if copies and installs and re.match(r"COPY\s+\.\s", lines[copies[0]], re.I) and copies[0] < installs[0]:
        findings.append(("layer-order", "source is copied before dependencies are installed: every edit reinstalls everything"))
    return findings


def scan_for_secrets(root):
    """Walk a folder and return (relative path, line number, kind, masked preview) for each hit."""
    root = Path(root)
    hits = []
    files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
    for path in files:
        if SKIP_DIRS & set(path.parts) or path.suffix in {".pyc", ".png", ".jpg"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for kind, pattern in SECRET_PATTERNS:
                match = pattern.search(line)
                if match:
                    secret = match.group(match.lastindex) if match.lastindex else match.group(0)
                    hits.append((str(path.relative_to(root.parent if root.is_file() else root)), number, kind, secret[:4] + "****"))
                    break
    return hits


@lesson("20.3/1", "Two static audits: a Dockerfile lint and a secret scan")
def main(ctx):
    problems = 0

    ctx.step("Dockerfile lint: the reference project")
    findings = lint_dockerfile((HERE / "project" / "Dockerfile").read_text(encoding="utf-8"))
    ctx.note("clean: 0 findings" if not findings else f"{len(findings)} finding(s)")
    for rule, message in findings:
        ctx.note(f"  FAIL {rule}: {message}")
    problems += len(findings)

    ctx.step("Dockerfile lint: samples/Dockerfile.bad (mistakes on purpose)")
    for rule, message in lint_dockerfile((HERE / "samples" / "Dockerfile.bad").read_text(encoding="utf-8")):
        ctx.note(f"  FAIL {rule}: {message}")

    ctx.step("Secret scan: the reference project")
    hits = scan_for_secrets(HERE / "project")
    ctx.note("clean: 0 findings (.env.example has an empty LLM_API_KEY on purpose)" if not hits else f"{len(hits)} finding(s)")
    for path, number, kind, preview in hits:
        ctx.note(f"  FAIL {path}:{number} {kind} {preview}")
    problems += len(hits)

    ctx.step("Secret scan: samples/leaky_config.py (invented secrets on purpose)")
    for path, number, kind, preview in scan_for_secrets(HERE / "samples" / "leaky_config.py"):
        ctx.note(f"  FAIL {path}:{number} {kind} {preview}")

    ctx.step("Result")
    if problems:
        ctx.note(f"{problems} problem(s) in the reference project: fix them before deploying.")
        sys.exit(1)
    ctx.note("The reference project passes both audits; the samples show what failing looks like.")
    ctx.note("Your turn: run these on your own project. Copy the two functions into your CI as a test.")


if __name__ == "__main__":
    main()
