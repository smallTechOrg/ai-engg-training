"""`run doctor`: check the machine, the settings, the endpoint and what the model can do."""

from __future__ import annotations

import importlib
import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

from rich.console import Console
from rich.markup import escape

from labkit.catalog import load_catalog
from labkit.client import get_client
from labkit.config import Settings, load_settings, mask, repo_root, state_dir
from labkit.errors import explain

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
STYLE = {PASS: "green", WARN: "yellow", FAIL: "red", SKIP: "dim"}
CORE_PACKAGES = ("openai", "dotenv", "rich")
CACHE = "doctor.json"
REPORT = "doctor-report.txt"


@dataclass
class Check:
    status: str
    name: str
    detail: str = ""
    fixes: list[str] = field(default_factory=list)


def check_python() -> Check:
    version = platform.python_version()
    where = f"Python {version} on {platform.system()} {platform.machine()}"
    if sys.version_info < (3, 11):
        return Check(FAIL, where, "Python 3.11 or newer is required.", ["Run the setup script again: it installs a suitable Python."])
    return Check(PASS, where)


def check_packages() -> Check:
    missing = []
    for name in CORE_PACKAGES:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        return Check(FAIL, "Core packages", "Missing: " + ", ".join(missing), ["Run the setup script again (setup.sh or setup.ps1)."])
    return Check(PASS, "Core packages installed")


def check_extras() -> list[Check]:
    from labkit.catalog import EXTRAS, install_command, extra_installed

    checks = []
    for extra in EXTRAS:
        lessons = [item.id for module in load_catalog() if extra in module.extras for item in module.lessons if item.runnable]
        if extra_installed(extra):
            checks.append(Check(PASS, f"Optional packages: {extra}"))
        else:
            used = f"needed by ready lessons {', '.join(lessons)}" if lessons else "not needed by any ready lesson yet"
            checks.append(Check(SKIP, f"Optional packages: {extra}", f"not installed ({used})", [install_command(extra)] if lessons else []))
    return checks


def check_services() -> list[Check]:
    """Infrastructure services: each is optional and only matters to the lessons that name it."""
    from labkit.services import SERVICES, probe

    used_by: dict[str, list[str]] = {}
    for module in load_catalog():
        for env in module.services:
            used_by.setdefault(env, []).append(module.id)
    checks = []
    for env, service in SERVICES.items():
        state, detail = probe(service)
        modules = ("module " + ", ".join(used_by[env])) if env in used_by else "no module yet"
        label = f"Service: {service.name}"
        if state == "ok":
            checks.append(Check(PASS, label, f"{detail} (used by {modules})"))
        elif state == "unset":
            checks.append(Check(SKIP, label, f"not set up (used by {modules})", [f"To use it: {service.start}"] if env in used_by else []))
        else:
            checks.append(Check(WARN, label, f"{detail} (used by {modules})", [f"Start it: {service.start}"]))
    return checks


def check_settings(settings: Settings) -> Check:
    missing = settings.missing()
    source = ".env file" if settings.env_file_exists else "environment variables (no .env file)"
    if missing:
        fixes = [f"Open {settings.env_file} and set: {', '.join(missing)}"]
        if not settings.env_file_exists:
            fixes.insert(0, "Copy .env.example to .env (the setup script does this for you).")
        return Check(FAIL, "Settings", "Not set: " + ", ".join(missing), fixes)
    key = "not set (fine for a local model)" if settings.key_is_stand_in else mask(settings.api_key)
    detail = f"from {source}: LLM_BASE_URL={settings.base_url}  LLM_MODEL={settings.model}  LLM_API_KEY={key}"
    return Check(PASS, "Settings", detail)


def _failure(name: str, exc: Exception, settings: Settings, status: str = FAIL) -> Check:
    explained = explain(exc, settings)
    if explained:
        return Check(status, name, explained.title, explained.fixes)
    return Check(status, name, f"{type(exc).__name__}: {' '.join(str(exc).split())[:200]}")


def probe_chat(client, settings: Settings) -> Check:
    try:
        response = client.chat.completions.create(
            model=settings.model,
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        )
    except Exception as exc:  # noqa: BLE001
        return _failure("Endpoint: a real chat call", exc, settings)
    text = (response.choices[0].message.content or "").strip()
    return Check(PASS, "Endpoint: a real chat call", f"model replied: {text[:60]!r}")


def probe_stream(client, settings: Settings) -> Check:
    name = "Capability: streaming"
    try:
        stream = client.chat.completions.create(
            model=settings.model,
            messages=[{"role": "user", "content": "Count from 1 to 5."}],
            stream=True,
            stream_options={"include_usage": True},
        )
        pieces = sum(1 for chunk in stream for choice in (chunk.choices or []) if getattr(choice.delta, "content", None))
    except Exception as exc:  # noqa: BLE001
        return _failure(name, exc, settings, WARN)
    if pieces == 0:
        return Check(WARN, name, "The endpoint accepted the request but streamed no text.")
    return Check(PASS, name, f"{pieces} chunks received")


def probe_tools(client, settings: Settings) -> Check:
    name = "Capability: tool calling"
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather for a city.",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
            },
        }
    ]
    try:
        response = client.chat.completions.create(
            model=settings.model,
            messages=[{"role": "user", "content": "What is the weather in Paris right now? Use the tool."}],
            tools=tools,
        )
    except Exception as exc:  # noqa: BLE001
        return _failure(name, exc, settings, WARN)
    calls = response.choices[0].message.tool_calls or []
    if not calls:
        return Check(WARN, name, "The model answered in text instead of calling the tool.", ["Tool lessons need a model that supports function calling: choose another LLM_MODEL for those."])
    return Check(PASS, name, f"model asked for {calls[0].function.name}({calls[0].function.arguments})")


def probe_json(client, settings: Settings) -> Check:
    name = "Capability: JSON output"
    try:
        response = client.chat.completions.create(
            model=settings.model,
            messages=[{"role": "user", "content": 'Return a JSON object with one key "ok" whose value is true.'}],
            response_format={"type": "json_object"},
        )
        json.loads(response.choices[0].message.content or "")
    except ValueError:
        return Check(WARN, name, "The reply was not valid JSON.", ["Structured-output lessons need a model with JSON mode."])
    except Exception as exc:  # noqa: BLE001
        return _failure(name, exc, settings, WARN)
    return Check(PASS, name)


def probe_embeddings(settings: Settings) -> Check:
    from labkit.catalog import extra_installed, install_command
    from labkit.embeddings import backend, embed

    name = "Capability: embeddings"
    kind, model = backend(settings)
    if kind == "local":
        if not extra_installed("rag"):
            return Check(SKIP, name, f"will run on this machine ({model}) once the 'rag' packages are installed", [install_command("rag")])
        try:
            vectors, _, _ = embed(["hello"], settings)
        except Exception as exc:  # noqa: BLE001
            return Check(WARN, name, f"local model {model} failed: {type(exc).__name__}", ["The first run downloads the model (about 70 MB): check your network or proxy."])
        return Check(PASS, name, f"on this machine with {model}: {len(vectors[0])} dimensions")
    try:
        client = get_client(settings, embeddings=True)
        result = client.embeddings.create(model=settings.embedding_model, input="hello")
    except Exception as exc:  # noqa: BLE001
        return _failure(name, exc, settings, WARN)
    return Check(PASS, name, f"{settings.embedding_model}: {len(result.data[0].embedding)} dimensions")


PROBES = {"stream": probe_stream, "tools": probe_tools, "json": probe_json}


def affected_lessons(capability: str) -> list[str]:
    return [item.id for module in load_catalog() for item in module.lessons if item.runnable and capability in item.needs]


def run_checks(offline: bool = False, on_check=None) -> tuple[list[Check], dict]:
    """Run every check; returns the checks and the capability cache."""
    checks: list[Check] = []
    capabilities: dict[str, bool | None] = {name: None for name in ("chat", "stream", "tools", "json", "embeddings")}

    def add(check: Check) -> Check:
        checks.append(check)
        if on_check:
            on_check(check)
        return check

    add(check_python())
    packages = add(check_packages())
    for check in check_extras():
        add(check)
    settings = load_settings()
    configured = add(check_settings(settings))
    if not offline:
        for check in check_services():
            add(check)

    if offline:
        add(Check(SKIP, "Endpoint and capability checks", "skipped (--offline)"))
    elif packages.status == FAIL or configured.status == FAIL:
        add(Check(SKIP, "Endpoint and capability checks", "skipped until the problems above are fixed"))
    else:
        client = get_client(settings)
        chat = add(probe_chat(client, settings))
        capabilities["chat"] = chat.status == PASS
        if chat.status == PASS:
            for capability, probe in PROBES.items():
                check = probe(client, settings)
                capabilities[capability] = check.status == PASS
                if check.status != PASS:
                    lessons = affected_lessons(capability)
                    check.fixes.append("Ready lessons affected: " + (", ".join(lessons) if lessons else "none yet"))
                add(check)
            embeddings = add(probe_embeddings(settings))
            capabilities["embeddings"] = None if embeddings.status == SKIP else embeddings.status == PASS
        else:
            add(Check(SKIP, "Capability checks", "skipped until the endpoint call works"))

    cache = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": settings.model,
        "base_url": settings.base_url,
        "offline": offline,
        "capabilities": capabilities,
    }
    return checks, cache


def load_cache() -> dict | None:
    path = state_dir(".labkit") / CACHE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def format_plain(checks: list[Check]) -> str:
    lines = []
    for check in checks:
        lines.append(f"{check.status:4}  {check.name}" + (f" - {check.detail}" if check.detail else ""))
        lines += [f"        fix: {fix}" for fix in check.fixes]
    return "\n".join(lines)


def main(args: list[str], console: Console | None = None) -> int:
    console = console or Console(highlight=False, soft_wrap=True)
    offline = "--offline" in args
    console.print("[bold]Doctor[/bold]: checking this machine, your settings and the model endpoint\n")

    def show(check: Check) -> None:
        style = STYLE[check.status]
        detail = f" [dim]- {escape(check.detail)}[/dim]" if check.detail else ""
        console.print(f"[{style}]{check.status:4}[/{style}]  {escape(check.name)}{detail}")
        for fix in check.fixes:
            console.print(f"        [yellow]fix:[/yellow] {escape(fix)}")

    checks, cache = run_checks(offline=offline, on_check=show)
    failed = sum(1 for check in checks if check.status == FAIL)
    warned = sum(1 for check in checks if check.status == WARN)

    try:
        path = state_dir(".labkit") / CACHE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except OSError:
        pass

    console.print()
    if failed:
        console.print(f"[bold red]{failed} problem(s) to fix.[/bold red] Fix the first FAIL above, then run the doctor again.")
    elif warned:
        console.print(f"[bold yellow]Ready, with {warned} limitation(s).[/bold yellow] Lessons that need a missing capability will say so.")
    else:
        console.print("[bold green]All good.[/bold green] Try the first lesson: ./run 01.1   (Windows: run 01.1)")

    if "--report" in args:
        header = f"Doctor report, {cache['checked_at']}\n{platform.platform()}\n\n"
        state_dir(REPORT).write_text(header + format_plain(checks) + "\n", encoding="utf-8")
        console.print(f"[dim]Report written to {REPORT} (contains no secrets): send it to your instructor.[/dim]")
    return 1 if failed else 0
