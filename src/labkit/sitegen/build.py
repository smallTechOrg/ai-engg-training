"""Build the read-only course site from the repo: curriculum.toml, lesson READMEs and scripts.

The build is a pure function of the repo (no clock, no network, no absolute paths), so building
twice gives identical files. Nothing about a lesson lives only in the site.
"""

from __future__ import annotations

import hashlib
import html
import json
import posixpath
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it.token import Token
from markupsafe import Markup

from labkit.catalog import EXTRAS, LessonInfo, ModuleInfo, load_catalog, scenario
from labkit.config import repo_root
from labkit.sitegen import mdrender
from labkit.sitegen.walkthrough import extract, match_step, split_output

HERE = Path(__file__).parent
SITE_TITLE = "AI engineering training"
BRANCH = "main"
SUPPORT_LINE_CAP = 200
SKIP_NAMES = {"__pycache__", ".DS_Store"}
SECTION_KIND = {
    "what-you-will-learn": "learn",
    "the-idea": "idea",
    "try-this": "try",
    "if-it-does-not-work": "help",
    "in-the-running-scenario": "scenario",
}
SCRIPT_HEADING = re.compile(r"^(\d+)\.\s*`?([\w./-]+\.py)`?\s*[:–-]?\s*(.*)$")
SCRIPT_MENTION = re.compile(r"(?<![\w/])(\d{2}_[a-z0-9_]+\.py)\b")
META_FIELD = re.compile(r"\*\*([^*]+?):\*\*\s*(.*?)(?=\s·\s\*\*|$)")
AUTO = object()


def normalise_remote(url: str) -> str | None:
    """https://github.com/owner/repo for an ssh or https GitHub remote, else None."""
    found = re.match(r"^(?:https?://(?:[^@/]+@)?|ssh://(?:[^@/]+@)?|git@)github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?/?$", url.strip())
    return f"https://github.com/{found.group(1)}" if found else None


def detect_repo_url(root: Path) -> str | None:
    try:
        done = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return normalise_remote(done.stdout) if done.returncode == 0 else None


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@dataclass
class BuildResult:
    pages: int = 0
    seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scripts: dict[str, str] = field(default_factory=dict)  # script id -> aligned | no-output | no-steps
    files: dict[str, bytes] = field(default_factory=dict)
    out: Path | None = None


class Site:
    def __init__(self, root: Path, repo_url: str | None):
        self.root = root
        self.repo_url = repo_url
        self.modules = load_catalog(root / "curriculum.toml")
        self.scenario = scenario(root / "curriculum.toml")
        self.result = BuildResult()
        self.pages: dict[str, str] = {}
        self.search: list[list[str]] = []
        self.md = mdrender.make_parser()
        self.env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
        self.lessons = [item for module in self.modules for item in module.lessons if item.runnable]
        self.module_url = {m.id: f"modules/{m.slug}/index.html" for m in self.modules}
        self.lesson_url = {i.id: f"modules/{i.module.slug}/{i.slug}/index.html" for i in self.lessons}
        # resolved repo paths that have a page of their own
        self.path_pages: dict[Path, str] = {root / "README.md": "about.html"}
        for module in self.modules:
            self.path_pages[module.path / "README.md"] = self.module_url[module.id]
            self.path_pages[module.path] = self.module_url[module.id]
        for item in self.lessons:
            self.path_pages[item.path / "README.md"] = self.lesson_url[item.id]
            self.path_pages[item.path] = self.lesson_url[item.id]
        self.path_pages[root / "CURRICULUM.md"] = "index.html#modules"

    # --- reporting --------------------------------------------------------------------

    def error(self, where: str, message: str) -> None:
        self.result.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.result.warnings.append(f"{where}: {message}")

    # --- urls -------------------------------------------------------------------------

    def gh(self, relpath: str, directory: bool = False) -> str | None:
        if not self.repo_url:
            return None
        return f"{self.repo_url}/{'tree' if directory else 'blob'}/{BRANCH}/{relpath}"

    def rel(self, page: str, target: str) -> str:
        """Relative URL from `page` to `target` (both site paths; target may carry #fragment)."""
        path, _, fragment = target.partition("#")
        start = posixpath.dirname(page) or "."
        link = posixpath.relpath(path, start) if path else posixpath.basename(page)
        return link + (f"#{fragment}" if fragment else "")

    def repo_rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    # --- markdown helpers -------------------------------------------------------------

    def resolve_link(self, href: str, base: Path, page: str, where: str) -> str | None:
        """New href for a README link; None means 'show as plain text'."""
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith("//"):
            return href
        if href.startswith("#"):
            return href
        raw, _, fragment = href.partition("#")
        target = (base / unquote(raw)).resolve()
        try:
            relative = target.relative_to(self.root)
        except ValueError:
            self.error(where, f"link '{href}' points outside the repository")
            return None
        if not target.exists():
            self.error(where, f"link '{href}' does not resolve (no {relative.as_posix()})")
            return None
        for known, site_path in self.path_pages.items():
            if known == target:
                if "#" in site_path and fragment == "":
                    return self.rel(page, site_path)
                return self.rel(page, site_path + (f"#{fragment}" if fragment else ""))
        url = self.gh(relative.as_posix(), directory=target.is_dir())
        return url + (f"#{fragment}" if fragment else "") if url else None

    def prepare(self, tokens: list[Token], base: Path, page: str, where: str) -> None:
        """Rewrite links and mark expected-output blocks, in place."""
        for index, token in enumerate(tokens):
            if mdrender.is_output_label(tokens, index):
                tokens[index].attrSet("class", "output-label")
                tokens[index + 3].meta["terminal"] = True
            if token.type == "inline" and token.children:
                self._rewrite_inline(token.children, base, page, where)

    def _rewrite_inline(self, children: list[Token], base: Path, page: str, where: str) -> None:
        plain_depth: list[bool] = []
        for child in children:
            if child.type == "link_open":
                href = child.attrGet("href") or ""
                new = self.resolve_link(href, base, page, where)
                if new is None:
                    child.tag = "span"
                    child.attrs = {"class": "nolink"}
                    plain_depth.append(True)
                else:
                    child.attrSet("href", new)
                    plain_depth.append(False)
            elif child.type == "link_close":
                if plain_depth.pop():
                    child.tag = "span"
            elif child.type == "image":
                src = child.attrGet("src") or ""
                if not re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I):
                    self.error(where, f"image '{src}' is not supported (use text or a mermaid diagram)")

    def render(self, tokens: list[Token], env: dict) -> Markup:
        return Markup(self.md.renderer.render(tokens, self.md.options, env))

    def inline(self, text: str) -> Markup:
        return Markup(self.md.renderInline(text))

    # --- page output ------------------------------------------------------------------

    def page(self, template: str, path: str, **context) -> None:
        depth = path.count("/")
        context.setdefault("has_mermaid", False)
        context.setdefault("toc", [])
        context.setdefault("crumbs", [])
        context.setdefault("current", {})
        body = self.env.get_template(template).render(
            href=lambda target: self.rel(path, target),
            root="../" * depth,
            page_path=path,
            site_title=SITE_TITLE,
            nav=self.nav_data(),
            repo_url=self.repo_url,
            **context,
        )
        self.pages[path] = body

    def nav_data(self) -> list[dict]:
        if not hasattr(self, "_nav"):
            self._nav = [
                {
                    "id": m.id,
                    "title": m.title,
                    "url": self.module_url[m.id],
                    "lessons": [{"id": i.id, "title": i.title, "status": i.status, "url": self.lesson_url.get(i.id)} for i in m.lessons],
                }
                for m in self.modules
            ]
        return self._nav

    def index(self, kind: str, title: str, url: str, context: str = "") -> None:
        self.search.append([kind, title, url, " ".join(context.split())[:240]])

    # --- the whole site ---------------------------------------------------------------

    def build(self) -> BuildResult:
        started = time.perf_counter()
        for module in self.modules:
            self.build_module(module)
        for item in self.lessons:
            self.build_lesson(item)
        self.build_home()
        self.build_about()
        self.page("search.html", "search.html", title="Search", current={})
        self.check_links()
        files: dict[str, bytes] = {path: text.encode("utf-8") for path, text in self.pages.items()}
        for asset in sorted((HERE / "static").iterdir()):
            files[f"assets/{asset.name}"] = asset.read_bytes()
        files["assets/search-index.js"] = ("window.COURSE_INDEX=" + json.dumps(sorted(self.search, key=lambda e: (e[2], e[0], e[1])), ensure_ascii=False, separators=(",", ":")) + ";\n").encode("utf-8")
        files[".nojekyll"] = b""
        self.result.files = files
        self.result.pages = len(self.pages)
        self.result.seconds = time.perf_counter() - started
        return self.result

    # --- home, about ------------------------------------------------------------------

    def build_home(self) -> None:
        readme = (self.root / "README.md").read_text(encoding="utf-8")
        promise = re.search(r"^# .*\n+(.+?)\n\n", readme, re.S)
        lead = " ".join(promise.group(1).split()) if promise else ""
        total = sum(len(m.lessons) for m in self.modules)
        ready = sum(m.count("ready") for m in self.modules)
        first = self.lessons[0] if self.lessons else None
        self.page(
            "home.html",
            "index.html",
            title="",
            lead=self.inline(lead),
            scenario=self.scenario,
            stats={"modules": len(self.modules), "lessons": total, "ready": ready},
            first=first,
            first_url=self.lesson_url.get(first.id) if first else None,
            modules=[self.module_card(m) for m in self.modules],
        )
        self.index("page", SITE_TITLE, "index.html", lead)

    def module_card(self, module: ModuleInfo) -> dict:
        return {
            "module": module,
            "url": self.module_url[module.id],
            "ready": module.count("ready"),
            "total": len(module.lessons),
            "extras": [e for e in module.extras if e != "all"],
            "all_extras": "all" in module.extras,
            "services": module.services,
        }

    def build_about(self) -> None:
        text = (self.root / "README.md").read_text(encoding="utf-8")
        env: dict = {}
        tokens = self.md.parse(text, env)
        self.prepare(tokens, self.root, "about.html", "README.md")
        body = self.render(tokens, env)
        self.page("about.html", "about.html", title="About this course", body=body, has_mermaid=bool(env.get("mermaid")))
        self.index("page", "About this course", "about.html", "How the course works, setup, commands, instructors")
        for n, token in enumerate(tokens):
            if token.type == "heading_open" and token.tag in ("h2", "h3"):
                inline = tokens[n + 1]
                self.index("heading", inline.content.strip("`"), f"about.html#{token.attrGet('id')}", "About")

    # --- modules ----------------------------------------------------------------------

    def build_module(self, module: ModuleInfo) -> None:
        path = self.module_url[module.id]
        readme = module.path / "README.md"
        body = Markup("")
        env: dict = {}
        if readme.is_file():
            text = readme.read_text(encoding="utf-8")
            text = re.sub(r"<!-- lessons:start.*?<!-- lessons:end -->", "", text, flags=re.S)
            tokens = self.md.parse(text, env)
            tokens = self._trim_module_tokens(tokens, module)
            self.prepare(tokens, module.path, path, f"modules/{module.slug}/README.md")
            body = self.render(tokens, env)
        else:
            self.error(f"modules/{module.slug}", "module README.md is missing")
        rows = []
        for item in module.lessons:
            rows.append({"lesson": item, "url": self.lesson_url.get(item.id)})
        index = self.module_url[module.id]
        position = self.modules.index(module)
        self.page(
            "module.html",
            path,
            title=f"{module.id} · {module.title}",
            module=module,
            rows=rows,
            body=body,
            extras=[e for e in module.extras if e != "all"],
            all_extras="all" in module.extras,
            prev_module=self.modules[position - 1] if position else None,
            next_module=self.modules[position + 1] if position + 1 < len(self.modules) else None,
            module_url=self.module_url,
            crumbs=[("Course", "index.html")],
            current={"module": module.id},
            has_mermaid=bool(env.get("mermaid")),
        )
        self.index("module", f"{module.id} · {module.title}", index, module.summary)

    def _trim_module_tokens(self, tokens: list[Token], module: ModuleInfo) -> list[Token]:
        """Drop what the module page already shows: title, summary, chips, the lesson list."""
        out: list[Token] = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.type == "heading_open" and token.tag == "h1":
                i += 3
                continue
            if token.type == "heading_open" and token.tag == "h2" and tokens[i + 1].content.strip() == "Lessons":
                i += 3
                continue
            if token.type == "paragraph_open":
                content = tokens[i + 1].content
                if content.strip() == module.summary.strip() or content.startswith(("**Optional packages:**", "**Services:**", "Back to the")):
                    i += 3
                    continue
            out.append(token)
            i += 1
        return out

    # --- lessons ----------------------------------------------------------------------

    def build_lesson(self, item: LessonInfo) -> None:
        where = f"modules/{item.module.slug}/{item.slug}"
        path = self.lesson_url[item.id]
        readme = item.path / "README.md"
        if not readme.is_file():
            self.error(where, f"{item.status} lesson {item.id} has no README.md")
            return
        text = readme.read_text(encoding="utf-8")
        env: dict = {}
        tokens = self.md.parse(text, env)
        self.prepare(tokens, item.path, path, f"{where}/README.md")

        # Split at top-level h2 headings.
        cuts = [i for i, t in enumerate(tokens) if t.type == "heading_open" and t.level == 0 and t.tag == "h2"]
        pre = tokens[: cuts[0]] if cuts else tokens
        sections = [tokens[start : (cuts[n + 1] if n + 1 < len(cuts) else len(tokens))] for n, start in enumerate(cuts)]

        meta: dict[str, str] = {}
        lead_tokens: list[Token] = []
        j = 0
        while j < len(pre):
            token = pre[j]
            if token.type == "heading_open" and token.tag == "h1":
                j += 3
                continue
            if token.type == "paragraph_open" and pre[j + 1].content.startswith("**Module:**"):
                for key, value in META_FIELD.findall(pre[j + 1].content):
                    meta[key.strip().lower()] = value.strip()
                j += 3
                continue
            lead_tokens.append(token)
            j += 1

        toc: list[dict] = []
        parts: list[dict] = []
        scripts_html: list[dict] = []
        scripts_seen: set[str] = set()
        mentioned = set(SCRIPT_MENTION.findall(text))
        for section in sections:
            title = section[1].content.strip()
            sid = section[0].attrGet("id") or slugify(title)
            # the README's own "Next:" line is replaced by the previous / next navigation
            for k in range(len(section) - 2, -1, -1):
                if section[k].type == "paragraph_open" and section[k + 1].content.startswith("**Next:**"):
                    del section[k : k + 3]
            if title == "Scripts":
                data = self.build_scripts(item, section, env, path, where, scripts_seen)
                parts.append({"kind": "scripts", "id": sid, "title": title, **data})
                toc.append({"id": sid, "title": title, "children": [{"id": s["id"], "title": s["file"]} for s in data["scripts"]]})
                scripts_html = data["scripts"]
                continue
            kind = SECTION_KIND.get(sid, "plain")
            parts.append({"kind": "prose", "cls": kind, "id": sid, "title": title, "html": self.render(section, env)})
            toc.append({"id": sid, "title": title, "children": []})
            self.index("heading", f"{item.id} · {title}", f"{path}#{sid}", item.title)
            for n, token in enumerate(section):
                if token.type == "heading_open" and token.tag == "h3":
                    inline = section[n + 1]
                    self.index("heading", inline.content.strip("`"), f"{path}#{token.attrGet('id')}", f"{item.id} {item.title}")

        # Sync checks between the README and the folder.
        actual = {p.name for p in item.scripts()}
        for name in sorted(mentioned):
            if name not in actual and not self._script_exists_anywhere(name):
                self.error(where, f"README mentions script {name}, which does not exist")
        for name in sorted(actual - scripts_seen):
            if not self._is_helper(item.path / name):
                self.error(where, f"script {name} is not described in README.md (no '### N. `{name}`' section)")

        support = self.supporting_files(item)
        if support:
            toc.append({"id": "supporting-files", "title": "Supporting files", "children": []})
        position = self.lessons.index(item)
        learn = next((p for p in parts if p.get("id") == "what-you-will-learn"), None)
        self.page(
            "lesson.html",
            path,
            title=f"{item.id} · {item.title}",
            lesson=item,
            module=item.module,
            meta=self.lesson_meta(item, meta),
            lead=self.render(lead_tokens, env) if lead_tokens else Markup(""),
            parts=parts,
            support=support,
            toc=toc,
            prev=self._neighbour(position - 1),
            next=self._neighbour(position + 1),
            github=self.gh(self.repo_rel(item.path), directory=True),
            readme_github=self.gh(self.repo_rel(readme)),
            crumbs=[("Course", "index.html"), (f"{item.module.id} · {item.module.title}", self.module_url[item.module.id])],
            current={"module": item.module.id, "lesson": item.id},
            has_mermaid=bool(env.get("mermaid")),
        )
        learn_text = ""
        if learn:
            learn_text = re.sub(r"<[^>]+>", " ", str(learn["html"]))
        self.index("lesson", f"{item.id} · {item.title}", path, f"{item.module.title}. {html.unescape(learn_text)}")
        for s in scripts_html:
            self.index("script", f"{item.id}/{s['n']} {s['file']}", f"{path}#{s['id']}", f"{item.title}. {s['plain_title']}")

    def _script_exists_anywhere(self, name: str) -> bool:
        return any(p.name == name for m in self.modules for i in m.lessons for p in i.scripts())

    def _is_helper(self, path: Path) -> bool:
        try:
            return not extract(path.read_text(encoding="utf-8")).is_lesson
        except SyntaxError:
            return False

    def _neighbour(self, index: int) -> dict | None:
        if 0 <= index < len(self.lessons):
            other = self.lessons[index]
            return {"id": other.id, "title": other.title, "url": self.lesson_url[other.id], "module": other.module.title}
        return None

    def lesson_meta(self, item: LessonInfo, meta: dict[str, str]) -> dict:
        packages_text = meta.get("packages", "")
        names = [n for n in re.findall(r"`([a-z_]+)`", packages_text) if n in EXTRAS]
        if not names and item.module.extras and "extra" in packages_text:
            names = [e for e in item.module.extras if e != "all"]
        services_text = meta.get("services") or meta.get("service") or meta.get("service (optional)") or ""
        services = re.findall(r"`([A-Z][A-Z0-9_]+)`", services_text)
        base_only = bool(re.match(r"^(none|base)", packages_text, re.I)) or not packages_text
        return {
            "time": meta.get("time", ""),
            "needs_text": meta.get("model needs", ""),
            "packages": names,
            "packages_text": packages_text,
            "base_only": base_only and not names,
            "services": services,
        }

    # --- scripts ----------------------------------------------------------------------

    def build_scripts(self, item: LessonInfo, section: list[Token], env: dict, page: str, where: str, seen: set[str]) -> dict:
        cuts = [i for i, t in enumerate(section) if t.type == "heading_open" and t.tag == "h3" and t.level == 0]
        intro_tokens = section[3 : cuts[0]] if cuts else section[3:]
        script_paths = item.scripts()
        scripts: list[dict] = []
        items: list[dict] = []
        for n, start in enumerate(cuts):
            group = section[start : (cuts[n + 1] if n + 1 < len(cuts) else len(section))]
            heading = group[1].content.strip()
            found = SCRIPT_HEADING.match(heading)
            if not found:
                if ".py" in heading:
                    self.error(where, f"Scripts heading '{heading}' is not of the form '### N. `file.py`: title'")
                items.append({"kind": "prose", "html": self.render(group, env)})
                continue
            number, name, rest = int(found.group(1)), found.group(2), found.group(3)
            path = item.path / name
            if not path.is_file():
                self.error(where, f"README describes script {name}, which does not exist")
                continue
            seen.add(name)
            if path not in script_paths:
                self.error(where, f"script {name} does not match the numbered-script pattern")
                continue
            card = self.script_card(item, path, script_paths.index(path) + 1, number, rest, group[3:], env, page, where)
            scripts.append(card)
            items.append(card)
        return {"intro": self.render(intro_tokens, env) if intro_tokens else Markup(""), "scripts": scripts, "cards": items}

    def script_card(self, item: LessonInfo, path: Path, position: int, number: int, rest: str, tokens: list[Token], env: dict, page: str, where: str) -> dict:
        name = path.name
        label = f"{item.id}/{position}"
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        source = raw.decode("utf-8").replace("\r\n", "\n")
        try:
            walk = extract(source)
        except SyntaxError as error:
            self.error(f"{where}/{name}", f"does not parse: {error}")
            walk = extract("")
        # README prose and expected outputs for this script
        prose: list[Token] = []
        outputs: list[tuple[Markup, str]] = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if mdrender.is_output_label(tokens, i):
                label_html = Markup(self.md.renderInline(tokens[i + 1].content))
                outputs.append((label_html, tokens[i + 3].content))
                i += 4
                continue
            if token.type == "fence" and not token.info.strip() and re.match(r"^(\./run|run |python )", token.content.strip()) and token.content.strip().count("\n") == 0:
                i += 1
                continue
            prose.append(token)
            i += 1
        prose_html = self.render(prose, env) if prose else Markup("")

        # Align output chunks with steps.
        by_step: dict[int, list] = {}
        loose: list = []  # output of steps that run inside helper functions
        for _, text in outputs:
            _, chunks, _ = split_output(text)
            for chunk in chunks:
                if not re.sub(r"[.\u2026\s]", "", chunk.title):
                    continue  # "Step 2: ..." is the author eliding steps, not a step
                step = match_step(walk.steps, chunk.title)
                if step is None and walk.helper_steps:
                    loose.append(chunk)
                elif step is None:
                    titles = "; ".join(s.label for s in walk.steps) or "(no ctx.step calls)"
                    self.error(f"{where}/README.md", f"script {name}: expected output has 'Step {chunk.number}: {chunk.title}' but the script's steps are: {titles}")
                else:
                    by_step.setdefault(step.index, []).append(chunk)
        aligned = bool(by_step)
        category = ("helper-steps" if loose else "no-steps") if not walk.steps else "aligned" if aligned else "no-output"
        self.result.scripts[label] = category
        if walk.steps and not aligned and not loose:
            self.warn(f"{where}/README.md", f"script {name} has steps but no step-aligned expected output")

        steps = []
        for step in walk.steps:
            chunks = by_step.get(step.index, [])
            output = ""
            if len(chunks) == 1:
                output = "\n".join(chunks[0].lines)
            elif chunks:
                output = "\n\n".join(f"Step {c.number}: {c.title}\n" + "\n".join(c.lines) for c in chunks)
            steps.append(
                {
                    "number": step.index,
                    "label": step.label,
                    "notes": [self.inline(n) for n in step.notes],
                    "comments": [self.inline(c) for c in step.comments if c],
                    "code": Markup(mdrender.code_block(step.code, "python", start=step.code_start, numbered=True)),
                    "lines": step.code.count("\n") + 1,
                    "output": Markup(mdrender.terminal_block(output, "What you will see")) if output.strip() else "",
                    "repeats": len(chunks) > 1,
                }
            )
        loose_text = "\n\n".join(f"Step {c.number}: {c.title}\n" + "\n".join(c.lines) for c in loose) if walk.steps else ""
        before = ""
        if walk.is_lesson and walk.before.strip():
            before = Markup(mdrender.code_block(walk.before, "python", start=walk.before_start, numbered=True))
        single = ""
        if not walk.steps:
            single = Markup(mdrender.code_block(walk.body, "python", start=walk.body_start, numbered=True))
        full = Markup(mdrender.code_block(source, "python", sha=sha, label=name))
        out_blocks = [(lab, Markup(mdrender.terminal_block(text, "Expected output"))) for lab, text in outputs]
        heading_title = self.inline(rest) if rest else Markup(html.escape(name))
        return {
            "n": number,
            "id": f"script-{number}",
            "file": name,
            "sha": sha,
            "plain_title": re.sub(r"[`*]", "", rest) or walk.heading,
            "title": heading_title,
            "intro": [self.inline(p) for p in walk.intro],
            "prose": prose_html,
            "run_unix": f"./run {label}",
            "run_windows": f"run {label}",
            "steps": steps,
            "before": before,
            "before_lines": walk.before.count("\n") + 1 if walk.before.strip() else 0,
            "single": single,
            "full": full,
            "outputs": out_blocks,
            "aligned": aligned,
            "no_output": not outputs,
            "github": self.gh(self.repo_rel(path)),
            "kind": "script",
            "single_output": [Markup(mdrender.terminal_block(t, "What you will see")) for _, t in outputs] if not walk.steps else [],
            "fallback_output": [Markup(mdrender.terminal_block(t, "What you will see")) for _, t in outputs] if (walk.steps and not aligned) else ([Markup(mdrender.terminal_block(loose_text, "What you will see"))] if loose_text else []),
            "category": category,
            "lines": source.count("\n") + 1,
        }

    # --- supporting files -------------------------------------------------------------

    def supporting_files(self, item: LessonInfo) -> list[dict]:
        scripts = set(item.scripts())
        found: list[dict] = []
        if not item.path.is_dir():
            return found
        for path in sorted(item.path.rglob("*"), key=lambda p: p.relative_to(item.path).as_posix()):
            if not path.is_file() or path in scripts or path.name == "README.md" or any(part in SKIP_NAMES for part in path.parts) or path.suffix == ".pyc":
                continue
            raw = path.read_bytes()
            if b"\0" in raw or len(raw) > 400_000:
                continue
            try:
                text = raw.decode("utf-8").replace("\r\n", "\n")
            except UnicodeDecodeError:
                continue
            lines = text.rstrip("\n").split("\n")
            shown = "\n".join(lines[:SUPPORT_LINE_CAP])
            relative = path.relative_to(item.path).as_posix()
            found.append(
                {
                    "name": relative,
                    "lines": len(lines),
                    "truncated": len(lines) > SUPPORT_LINE_CAP,
                    "cap": SUPPORT_LINE_CAP,
                    "html": Markup(mdrender.code_block(shown, "", filename=relative, sha=hashlib.sha256(raw).hexdigest(), label=relative)),
                    "github": self.gh(self.repo_rel(path)),
                }
            )
        return found

    # --- link check -------------------------------------------------------------------

    def check_links(self) -> None:
        ids = {path: set(re.findall(r'\bid="([^"]+)"', body)) for path, body in self.pages.items()}
        assets = {f"assets/{p.name}" for p in (HERE / "static").iterdir()} | {"assets/search-index.js"}
        for path, body in sorted(self.pages.items()):
            for url in re.findall(r'(?:href|src)="([^"]+)"', body):
                if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", url, re.I):
                    continue
                target, _, fragment = html.unescape(url).partition("#")
                if target:
                    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
                    if resolved not in self.pages and resolved not in assets:
                        self.error(path, f"link '{url}' does not resolve")
                        continue
                else:
                    resolved = path
                if fragment and resolved in ids and fragment not in ids[resolved]:
                    self.error(path, f"link '{url}' points to a missing anchor")


def write_site(files: dict[str, bytes], out: Path) -> None:
    import shutil

    if out.exists():
        shutil.rmtree(out)
    for path, data in sorted(files.items()):
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def build_site(out: Path, *, strict: bool = False, repo_url=AUTO, root: Path | None = None, write: bool = True) -> BuildResult:
    """Build the site into `out`. Errors are collected; with `strict` the caller decides the exit code."""
    root = root or repo_root()
    url = detect_repo_url(root) if repo_url is AUTO else repo_url
    site = Site(root, url)
    result = site.build()
    result.out = out
    if write and not (strict and result.errors):
        write_site(result.files, out)
    return result
