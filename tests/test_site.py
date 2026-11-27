"""The course site: built from the repo, never hand-edited, so these tests keep it in sync."""

from __future__ import annotations

import hashlib
import posixpath
import re
from pathlib import Path

import pytest

pytest.importorskip("markdown_it", reason="the 'docs' extra is not installed (uv sync --extra docs)")
pytest.importorskip("mdit_py_plugins", reason="the 'docs' extra is not installed (uv sync --extra docs)")
pytest.importorskip("jinja2", reason="the 'docs' extra is not installed (uv sync --extra docs)")
pytest.importorskip("pygments", reason="the 'docs' extra is not installed (uv sync --extra docs)")

from labkit.catalog import load_catalog  # noqa: E402
from labkit.config import repo_root  # noqa: E402
from labkit.sitegen.build import build_site, normalise_remote  # noqa: E402
from labkit.sitegen.walkthrough import extract, split_output  # noqa: E402

ROOT = repo_root()


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    result = build_site(out / "a", strict=True, repo_url="https://github.com/example/course")
    assert not result.errors, "\n".join(result.errors)
    return out / "a", result, out


def page_text(out: Path, rel: str) -> str:
    return (out / rel).read_text(encoding="utf-8")


def test_every_runnable_lesson_has_a_page(built):
    out, _, _ = built
    for module in load_catalog():
        assert (out / "modules" / module.slug / "index.html").is_file()
        for item in module.lessons:
            if item.runnable:
                assert (out / "modules" / module.slug / item.slug / "index.html").is_file(), item.id


def test_script_source_hashes_match_the_files(built):
    out, _, _ = built
    for module in load_catalog():
        for item in module.lessons:
            if not item.runnable:
                continue
            html = page_text(out, f"modules/{module.slug}/{item.slug}/index.html")
            hashes = set(re.findall(r'<div class="codeblock" data-sha256="([0-9a-f]{64})"', html))
            for script in item.scripts():
                assert hashlib.sha256(script.read_bytes()).hexdigest() in hashes, script


def test_two_builds_are_byte_identical(built, tmp_path):
    out, _, _ = built
    build_site(tmp_path / "b", repo_url="https://github.com/example/course")
    first = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    second = {p.relative_to(tmp_path / "b").as_posix(): p.read_bytes() for p in (tmp_path / "b").rglob("*") if p.is_file()}
    assert first.keys() == second.keys()
    assert [k for k in first if first[k] != second[k]] == []


def test_no_absolute_paths_or_localhost(built):
    out, _, _ = built
    for path in out.rglob("*"):
        if path.is_file() and path.suffix in (".html", ".js", ".css"):
            text = path.read_text(encoding="utf-8")
            assert str(ROOT) not in text, path
            # Lesson prose may mention localhost; the site's own links, scripts and styles must not.
            if path.parent.name == "assets" and path.name != "search-index.js":
                assert "localhost" not in text and "127.0.0.1" not in text, path
            assert not re.search(r'(?:href|src)="/(?!/)', text), path
            if path.suffix == ".html":
                assert not re.search(r'<(?:link|script)[^>]+(?:localhost|127\.0\.0\.1)', text), path


def test_every_relative_link_and_asset_resolves(built):
    out, _, _ = built
    for page in out.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        for url in re.findall(r'(?:href|src)="([^"]+)"', text):
            if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", url, re.I):
                continue
            target = url.split("#")[0]
            resolved = Path(posixpath.normpath(posixpath.join(page.parent.as_posix(), target)))
            assert resolved.is_file(), f"{page.relative_to(out)} -> {url}"


def test_search_index_covers_every_lesson(built):
    out, _, _ = built
    index = page_text(out, "assets/search-index.js")
    assert index.startswith("window.COURSE_INDEX=")
    for module in load_catalog():
        for item in module.lessons:
            if item.runnable:
                assert f"modules/{module.slug}/{item.slug}/index.html" in index, item.id


def test_first_lesson_walkthrough_has_three_steps_with_output(built):
    out, _, _ = built
    html = page_text(out, "modules/01-foundations/01-first-llm-call/index.html")
    script = html.split('id="script-1"', 1)[1].split('id="script-2"', 1)[0]
    assert len(re.findall(r'<li class="step">', script)) == 3
    assert len(re.findall(r'<span class="termtitle">What you will see</span>', script.split('id="script-1-p2"')[0])) == 3


def test_mermaid_pages_keep_the_diagram_source_visible(built):
    out, _, _ = built
    html = page_text(out, "modules/04-rag-by-hand/01-the-rag-pipeline/index.html")
    assert '<pre class="mermaid"' in html and "flowchart LR" in html and "diagrams.js" in html
    assert "mermaid@11.4.1" in page_text(out, "assets/diagrams.js")


def test_github_links_are_omitted_without_a_remote(tmp_path):
    result = build_site(tmp_path / "s", repo_url=None, write=True)
    assert not result.errors
    assert "github.com" not in page_text(tmp_path / "s", "modules/01-foundations/01-first-llm-call/index.html")


def test_remote_urls_are_normalised():
    assert normalise_remote("git@github.com:o/r.git") == "https://github.com/o/r"
    assert normalise_remote("https://user:tok@github.com/o/r.git") == "https://github.com/o/r"
    assert normalise_remote("ssh://git@github.com/o/r") == "https://github.com/o/r"
    assert normalise_remote("https://example.org/o/r") is None


def test_assets_stay_small():
    total = sum(p.stat().st_size for p in (ROOT / "src/labkit/sitegen/static").iterdir())
    assert total < 150_000


# --- the step extractor -------------------------------------------------------------------

SCRIPT = '''"""9.9/1  Demo title

Intro paragraph one.

Run it:   ./run 9.9/1
     or:  python x.py
"""
import os

LIMIT = 3


@lesson("9.9/1", "Demo")
def main(ctx):
    # Leading comment
    ctx.step("First")
    ctx.note("A plain note")
    ctx.note(f"runtime {LIMIT}")
    with open(os.devnull) as handle:
        ctx.step(f"Nested {LIMIT} items")
        handle.read()
    ctx.step("Last")
'''


def test_extractor_finds_steps_notes_comments_and_the_prelude():
    walk = extract(SCRIPT)
    assert [s.title for s in walk.steps] == ["First", "Nested items", "Last"]
    assert walk.steps[1].label == "Nested … items"
    assert walk.steps[0].notes == ["A plain note"] and walk.steps[0].comments == ["Leading comment"]
    assert "LIMIT = 3" in walk.before and "def main" not in walk.before
    assert walk.heading.endswith("Demo title") and walk.intro == ["Intro paragraph one."]
    assert walk.steps[1].pattern.fullmatch("Nested 7 items")


def test_extractor_handles_async_main_and_scripts_without_steps():
    asynchronous = extract('"""x"""\n@lesson("1/1", "t")\nasync def main(ctx):\n    ctx.step("One")\n    await x()\n')
    assert [s.title for s in asynchronous.steps] == ["One"]
    plain = extract('"""x"""\n@lesson("1/1", "t")\ndef main(ctx):\n    print(1)\n')
    assert plain.is_lesson and plain.steps == []
    helper = extract('"""x"""\ndef thing():\n    return 1\n')
    assert not helper.is_lesson


def test_output_splitter_splits_on_step_headings():
    text = "banner\nStep 1: Write ────────\nline a\n\nStep 2: Send it\nline b\nRun summary: x\nLog: y\n"
    head, chunks, footer = split_output(text)
    assert head == ["banner"]
    assert [(c.number, c.title, c.lines) for c in chunks] == [(1, "Write", ["line a"]), (2, "Send it", ["line b"])]
    assert footer == ["Run summary: x", "Log: y"]
