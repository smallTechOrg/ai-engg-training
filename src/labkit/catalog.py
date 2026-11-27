"""Read curriculum.toml: the list of modules and lessons and their status."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from labkit.config import repo_root

STATUSES = ("ready", "draft", "planned")

# Optional package groups (pyproject extras) and one import that proves each is installed.
EXTRAS = {
    "rag": ("fastembed", "chromadb", "faiss", "rank_bm25", "networkx"),
    "apps": ("fastapi", "uvicorn", "streamlit", "gradio"),
    "langchain": ("langchain", "langchain_openai", "langchain_community"),
    "langgraph": ("langgraph", "langchain_openai"),
    "mcp": ("mcp",),
    "crewai": ("crewai",),
    "observability": ("opentelemetry", "prometheus_client"),
    "guardrails": ("presidio_analyzer", "presidio_anonymizer"),
}
# Which extra provides an importable top-level module (for friendly "install this" errors).
MODULE_TO_EXTRA: dict[str, str] = {}
for _extra, _modules in EXTRAS.items():
    for _module in _modules:
        MODULE_TO_EXTRA.setdefault(_module, _extra)  # first group that lists a module wins
MODULE_TO_EXTRA.update({"numpy": "rag", "langchain_core": "langchain", "langchain_text_splitters": "langchain", "langgraph_checkpoint": "langgraph", "httpx": "apps", "starlette": "apps"})


def install_command(extra: str) -> str:
    return f"uv sync --extra {extra}   (or everything: ./setup.sh --all, Windows: setup -All)"


def extra_installed(extra: str) -> bool:
    import importlib.util

    return all(importlib.util.find_spec(name) is not None for name in EXTRAS.get(extra, ()))
SCRIPT_PATTERN = "[0-9][0-9]_*.py"


@dataclass
class LessonInfo:
    id: str
    slug: str
    title: str
    status: str
    needs: list[str]
    module: "ModuleInfo" = field(repr=False)

    @property
    def path(self) -> Path:
        return self.module.path / self.slug

    def scripts(self) -> list[Path]:
        return sorted(self.path.glob(SCRIPT_PATTERN)) if self.path.is_dir() else []

    @property
    def runnable(self) -> bool:
        return self.status in ("ready", "draft")


@dataclass
class ModuleInfo:
    id: str
    slug: str
    title: str
    summary: str
    extras: list[str]
    services: list[str]
    lessons: list[LessonInfo] = field(default_factory=list)

    @property
    def path(self) -> Path:
        return repo_root() / "modules" / self.slug

    def count(self, status: str) -> int:
        return sum(1 for item in self.lessons if item.status == status)


def load_catalog(path: Path | None = None) -> list[ModuleInfo]:
    path = path or repo_root() / "curriculum.toml"
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    modules: list[ModuleInfo] = []
    for raw in data.get("module", []):
        module = ModuleInfo(
            id=raw["id"],
            slug=raw["slug"],
            title=raw["title"],
            summary=raw.get("summary", ""),
            extras=list(raw.get("extras", [])),
            services=list(raw.get("services", [])),
        )
        for item in raw.get("lesson", []):
            if item["status"] not in STATUSES:
                raise ValueError(f"Lesson {item['id']}: unknown status '{item['status']}'")
            module.lessons.append(
                LessonInfo(item["id"], item["slug"], item["title"], item["status"], list(item.get("needs", [])), module)
            )
        modules.append(module)
    return modules


def scenario(path: Path | None = None) -> str:
    path = path or repo_root() / "curriculum.toml"
    with path.open("rb") as handle:
        return tomllib.load(handle).get("scenario", "")


TARGET = re.compile(r"^(\d{1,2})(?:\.(\d{1,2}))?(?:/(\d{1,2}))?$")


def looks_like_target(text: str) -> bool:
    return bool(TARGET.match(text))


def find_module(modules: list[ModuleInfo], module_id: str) -> ModuleInfo | None:
    wanted = module_id.zfill(2)
    return next((m for m in modules if m.id == wanted), None)


def find_lesson(modules: list[ModuleInfo], target: str) -> tuple[LessonInfo | None, int | None]:
    """Resolve '01.1' or '1.1/2' to (lesson, script number or None)."""
    match = TARGET.match(target)
    if not match or match.group(2) is None:
        return None, None
    lesson_id = f"{match.group(1).zfill(2)}.{int(match.group(2))}"
    script = int(match.group(3)) if match.group(3) else None
    for module in modules:
        for item in module.lessons:
            if item.id == lesson_id:
                return item, script
    return None, script


BADGE = {"ready": "✅ ready", "draft": "🚧 draft", "planned": "⬜ planned"}


def render_map(modules: list[ModuleInfo], scenario_name: str = "") -> str:
    """The text of CURRICULUM.md."""
    total = sum(len(m.lessons) for m in modules)
    ready = sum(m.count("ready") for m in modules)
    lines = [
        "# Curriculum map",
        "",
        "<!-- Generated from curriculum.toml by `./run map`. Do not edit by hand. -->",
        "",
        f"{len(modules)} modules, {total} lessons, {ready} ready. "
        f"Each lesson shows a concept on its own, then applies it to the running scenario: **{scenario_name}**.",
        "",
        "| Status | Meaning |",
        "|---|---|",
        "| ✅ ready | Written, tested, runnable |",
        "| 🚧 draft | Runnable but still being refined |",
        "| ⬜ planned | Outlined; not written yet |",
        "",
        "## Modules",
        "",
        "| # | Module | Lessons ready |",
        "|---|---|---|",
    ]
    for module in modules:
        lines.append(f"| {module.id} | [{module.title}](modules/{module.slug}/README.md) | {module.count('ready')} / {len(module.lessons)} |")
    for module in modules:
        lines += ["", f"## {module.id} · {module.title}", "", module.summary, ""]
        extra = []
        if module.extras:
            extra.append("Optional packages: " + ", ".join(f"`{name}`" for name in module.extras))
        if module.services:
            extra.append("Services: " + ", ".join(f"`{name}`" for name in module.services))
        if extra:
            lines += [" · ".join(extra), ""]
        lines += ["| Lesson | Title | Status | Model needs |", "|---|---|---|---|"]
        for item in module.lessons:
            title = f"[{item.title}](modules/{module.slug}/{item.slug}/README.md)" if item.runnable else item.title
            needs = ", ".join(item.needs) or "-"
            lines.append(f"| {item.id} | {title} | {BADGE[item.status]} | {needs} |")
    return "\n".join(lines) + "\n"


START, END = "<!-- lessons:start (generated by `./run map`) -->", "<!-- lessons:end -->"


def render_lesson_table(module: ModuleInfo) -> str:
    lines = [START, "", "| Lesson | Title | Status |", "|---|---|---|"]
    for item in module.lessons:
        title = f"[{item.title}]({item.slug}/README.md)" if item.runnable else item.title
        lines.append(f"| {item.id} | {title} | {BADGE[item.status]} |")
    lines += ["", END]
    return "\n".join(lines)


def render_module_readme(module: ModuleInfo, scenario_name: str = "") -> str:
    """A starting README for a module. Only the lesson table is regenerated afterwards."""
    lines = [f"# {module.id} · {module.title}", "", module.summary, ""]
    if module.extras:
        lines += ["**Optional packages:** " + ", ".join(f"`{name}`" for name in module.extras) + " (installed when this module is built).", ""]
    if module.services:
        lines += ["**Services:** " + ", ".join(f"`{name}`" for name in module.services) + ", each set in `.env`; lessons skip cleanly when one is missing.", ""]
    lines += ["## Lessons", "", render_lesson_table(module), ""]
    lines += [
        "## Running scenario",
        "",
        f"Every lesson ends by applying its idea to the **{scenario_name}**; the module closes with a capstone on it.",
        "",
        "Back to the [curriculum map](../../CURRICULUM.md).",
    ]
    return "\n".join(lines) + "\n"


def sync_module_readme(existing: str | None, module: ModuleInfo, scenario_name: str = "") -> str:
    """Create a module README, or refresh only its generated lesson table."""
    if existing is None or START not in existing or END not in existing:
        return render_module_readme(module, scenario_name) if existing is None else existing
    head, rest = existing.split(START, 1)
    tail = rest.split(END, 1)[1]
    return head + render_lesson_table(module) + tail
