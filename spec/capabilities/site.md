# Capability: course site (read-only, follow-along)

**Goal.** A website that explains every lesson in depth, in a better format than a README, for
people who follow along without running anything. Learners cannot trigger commands from it.
It is **generated from the repo and never hand-edited**, so it cannot drift from the lessons.

## Sources of truth (nothing about a lesson lives only in the site)

| Site content | Comes from |
|---|---|
| Module and lesson structure, status, model needs, packages, services | `curriculum.toml` |
| Concept prose, diagrams, "try this", expected output | each lesson's `README.md` |
| Code | the lesson's numbered scripts and supporting files, shown verbatim |
| Step-by-step walkthrough | derived from the script itself: `@lesson` docstring, `ctx.step(...)` titles, `ctx.note(...)` text, comments |
| Output beside each step | the README's "Expected output" block, split on its `Step N:` headings |

## Pages

- **Home**: course title, one-line promise, the running scenario, "Start here" (-> 00.1), a card per
  module (number, title, summary, ready count, package/service chips).
- **Module page**: summary, chips, lesson list with status and model needs, module prose.
- **Lesson page**: header (id, title, time, model needs, packages, status), sticky "On this page"
  list, the README rendered well (callouts, diagrams, tables), previous/next lesson, link to the
  folder on GitHub (when the origin remote is known).
- **Script walkthrough** (inside the lesson page, one per script): intro from the docstring; the run
  command shown as text with a copy button (`./run 04.1/2`, Windows `run 04.1/2`); then **step
  cards**: step number and title, the narrative (`ctx.note` text and leading comments), the code of
  that step with line numbers and highlighting, and the matching output chunk ("What you will see").
  A "Before the steps" card holds constants and helpers. Tabs: Walkthrough · Full code · Output.
  Expand/collapse all. Scripts without `ctx.step` show one card.
- **Supporting files** (compose files, Dockerfiles, JSON, kb/*.md, helper servers): collapsible, verbatim,
  capped at 200 lines with a link to the full file on GitHub.
- **About**: the repo README rendered in full. **Search**: Ctrl/Cmd-K palette over lessons, headings and scripts.

## Behaviour and UX

- Static files only; no backend, no accounts, no analytics, no network at build time.
- Works opened from disk (`file://`), from `python -m http.server`, and under a sub-path (GitHub Pages
  project site): **all links relative**; the search index is a `.js` file, not fetched JSON.
- Light and dark (follows the system, toggle remembered; wrap storage access in try/catch).
- Responsive from 360 px: sidebars collapse to a menu; no horizontal page scroll (code scrolls inside its box).
- Accessible: semantic headings, skip link, visible focus, keyboard-operable tabs and cards, AA contrast,
  `prefers-reduced-motion` respected.
- Fast and light: vanilla CSS and JS, system fonts, under 150 KB of assets. Diagrams use Mermaid from a
  pinned CDN version; if it cannot load, show the diagram source instead (never a blank gap).
- Copy that reads like a good course: plain labels, no jargon, sentence case.

## Tooling

- Python only (3.11+, no Node): `markdown-it-py`, `mdit-py-plugins`, `jinja2`, `pygments`, in a new
  `docs` extra of `pyproject.toml` (so `./setup.sh --all` includes it).
- Code in `src/labkit/sitegen/` (generator, templates, static assets). Output to `site-dist/` (ignored).
- Launcher: `./run site build [--out DIR] [--strict]` and `./run site serve [--port N]`
  (serves on 127.0.0.1; port 0 picks a free one and prints the URL).

## Staying in sync (enforced by tests, run in CI)

1. The build is a pure function of the repo; running it twice gives identical files.
2. Every ready/draft lesson has a page; every script's full source appears verbatim (a source hash is
   embedded as a data attribute and compared in tests with the file's hash).
3. `--strict` fails the build on: a README mentioning a script that does not exist; a script missing from
   its README; an internal link that does not resolve; an expected-output `Step N: title` that does not
   match the script's `ctx.step` title; a script with steps whose README has no step-aligned output
   (reported as a warning count, not an error).
4. README links to other lessons or modules become site links; links to repo files become GitHub links
   (or plain text when the remote is unknown).
5. CI: the base job runs `./run site build --strict` and uploads the site as an artifact. A separate
   `pages.yml` deploys it to GitHub Pages **only when the repository variable `PUBLISH_SITE` is `true`**
   and Pages is set to "GitHub Actions" in repo settings (opt-in; nothing is published otherwise).
