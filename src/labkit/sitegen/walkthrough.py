"""Turn a lesson script into walkthrough steps, and split README output blocks by step.

Pure functions, no I/O: given source text (or an output block) they return plain data.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass
class Step:
    index: int
    title: str  # literal text of the title (f-string expressions dropped)
    label: str  # display form: expressions shown as an ellipsis
    pattern: re.Pattern  # matches the real runtime title
    first_line: int  # 1-based, first line of this step's code (inclusive)
    last_line: int  # inclusive
    notes: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    dynamic: bool = False  # the title is only known at run time (a variable)
    code: str = ""  # dedented source of the step
    code_start: int = 1  # file line number of the first code line


@dataclass
class Walkthrough:
    intro: list[str]  # paragraphs of the module docstring (run instructions removed)
    heading: str  # first docstring line, e.g. "01.1/1  Hello, LLM"
    before: str  # source between the docstring and `main` (imports, constants, helpers)
    before_start: int
    steps: list[Step]
    is_lesson: bool  # has an @lesson function
    helper_steps: bool  # ctx.step is also called from helper functions outside main
    body: str  # everything after the docstring (used when there are no steps)
    body_start: int


def _ctx_name(func: ast.AST) -> str:
    args = func.args.args  # type: ignore[attr-defined]
    return args[0].arg if args else "ctx"


def _is_lesson_decorator(node: ast.expr) -> bool:
    target = node.func if isinstance(node, ast.Call) else node
    name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else ""
    return name == "lesson"


def _find_main(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(_is_lesson_decorator(d) for d in node.decorator_list):
            return node
    return None


def _lit(text: str) -> str:
    """Regex for literal text that tolerates different runs of whitespace."""
    words = text.split()
    body = r"\s+".join(re.escape(w) for w in words)
    return (r"\s*" if text[:1].isspace() else "") + body + (r"\s*" if text[-1:].isspace() and words else "")


def _title_parts(node: ast.expr) -> tuple[str, str, re.Pattern] | None:
    """(literal text, display label, matching regex) for a string or f-string node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        text = " ".join(node.value.split())
        return text, text, re.compile(_lit(text))
    if isinstance(node, ast.JoinedStr):
        literal, label, regex = [], [], []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                literal.append(part.value)
                label.append(part.value)
                regex.append(_lit(part.value))
            else:
                label.append("…")
                regex.append(".*?")
        return (
            " ".join("".join(literal).split()),
            " ".join("".join(label).split()),
            re.compile("".join(regex), re.DOTALL),
        )
    return None


def _constant_text(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return " ".join(node.value.split())
    return None


def _attr_call(node: ast.AST, ctx: str, attr: str) -> ast.Call | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attr
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == ctx
        and node.args
    ):
        return node
    return None


def _leading_comments(lines: list[str], line_no: int) -> tuple[list[str], int]:
    """Comment lines directly above `line_no` (1-based). Returns (texts, first comment line)."""
    texts: list[str] = []
    index = line_no - 2
    first = line_no
    while index >= 0 and lines[index].strip().startswith("#"):
        texts.append(lines[index].strip().lstrip("#").strip())
        first = index + 1
        index -= 1
    return list(reversed(texts)), first


def docstring_parts(doc: str | None) -> tuple[str, list[str]]:
    """(heading line, intro paragraphs) with the 'Run it' boilerplate removed."""
    if not doc:
        return "", []
    lines = doc.strip().splitlines()
    heading = lines[0].strip()
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines[1:] + [""]:
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    keep = [p for p in paragraphs if not re.match(r"^(Run it:|or:|Add --raw)", p)]
    return heading, keep


def _dedent(lines: list[str]) -> list[str]:
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]
    cut = min(indents) if indents else 0
    return [line[cut:] if line.strip() else "" for line in lines]


def extract(source: str) -> Walkthrough:
    """Parse a lesson script. Raises SyntaxError if the source does not parse."""
    tree = ast.parse(source)
    lines = source.splitlines()
    doc = ast.get_docstring(tree)
    heading, intro = docstring_parts(doc)
    first = tree.body[0] if tree.body else None
    has_doc = isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) and isinstance(first.value.value, str)
    body_start = (first.end_lineno + 1) if has_doc else 1
    while body_start <= len(lines) and not lines[body_start - 1].strip():
        body_start += 1
    body = "\n".join(lines[body_start - 1 :]).rstrip()

    main = _find_main(tree)
    if main is None:
        return Walkthrough(intro, heading, "", body_start, [], False, False, body, body_start)

    ctx = _ctx_name(main)
    calls = [n for n in ast.walk(main) if _attr_call(n, ctx, "step")]
    calls.sort(key=lambda n: (n.lineno, n.col_offset))
    decorator_line = min([d.lineno for d in main.decorator_list] + [main.lineno])
    before_lines = lines[body_start - 1 : decorator_line - 1]
    before = "\n".join(before_lines).rstrip()

    # The statement that holds each step call, so a multi-line call is not cut in half.
    main_end = main.end_lineno
    body_stmts = [s for s in main.body if not (isinstance(s, ast.Expr) and isinstance(getattr(s, "value", None), ast.Constant))]
    steps: list[Step] = []
    starts: list[int] = []
    inside = {id(n) for n in ast.walk(main)}
    helper_steps = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "step" and isinstance(n.func.value, ast.Name) and n.args and id(n) not in inside
        for n in ast.walk(tree)
    )
    for number, call in enumerate(calls, start=1):
        parts = _title_parts(call.args[0])
        dynamic = parts is None
        title, label, pattern = parts or ("", "Step titled at run time", re.compile(r".+", re.DOTALL))
        comments, comment_start = _leading_comments(lines, call.lineno)
        step = Step(len(steps) + 1, title or f"Step {len(steps) + 1}", label or f"Step {len(steps) + 1}", pattern, call.lineno, main_end, comments=comments, dynamic=dynamic)
        steps.append(step)
        starts.append(comment_start)

    # Code ranges: from the step call to just before the next step's leading comments.
    for position, step in enumerate(steps):
        end = starts[position + 1] - 1 if position + 1 < len(steps) else main_end
        step.last_line = max(step.first_line, end)
    if steps and body_stmts:
        # Statements in main before the first step belong to step 1's code.
        head = body_stmts[0].lineno
        if head < steps[0].first_line:
            steps[0].first_line = head
            steps[0].comments = []

    for step in steps:
        chunk = lines[step.first_line - 1 : step.last_line]
        while chunk and not chunk[-1].strip():
            chunk.pop()
        step.code = "\n".join(_dedent(chunk))
        step.code_start = step.first_line
        for node in ast.walk(main):
            call = _attr_call(node, ctx, "note")
            if call is not None and step.first_line <= call.lineno <= step.last_line:
                text = _constant_text(call.args[0])
                if text and text not in step.notes:
                    step.notes.append(text)
    return Walkthrough(intro, heading, before, body_start, steps, True, helper_steps, body, body_start)


# --- README expected-output splitting ---------------------------------------------------

STEP_HEADING = re.compile(r"^\s*(?:[\u2500-\u257f]+\s*)?Step (\d+):\s*(.*?)(?:\s*[\u2500-\u257f]+)?\s*$")
FOOTER = re.compile(r"^(Run summary:|Log:)")


@dataclass
class OutputChunk:
    number: int
    title: str
    lines: list[str]


def split_output(text: str) -> tuple[list[str], list[OutputChunk], list[str]]:
    """Split an expected-output block on its `Step N: title` lines.

    Returns (lines before the first step, chunks, trailing summary lines).
    """
    head: list[str] = []
    chunks: list[OutputChunk] = []
    for line in text.splitlines():
        found = STEP_HEADING.match(line)
        if found:
            chunks.append(OutputChunk(int(found.group(1)), found.group(2).strip(), []))
        elif chunks:
            chunks[-1].lines.append(line)
        else:
            head.append(line)
    footer: list[str] = []
    if chunks:
        last = chunks[-1].lines
        for index, line in enumerate(last):
            if FOOTER.match(line):
                footer = last[index:]
                del last[index:]
                break
    for chunk in chunks:
        while chunk.lines and not chunk.lines[-1].strip():
            chunk.lines.pop()
        while chunk.lines and not chunk.lines[0].strip():
            chunk.lines.pop(0)
    return head, chunks, footer


def match_step(steps: list[Step], title: str) -> Step | None:
    """The code step whose title is `title` (an output heading).

    f-string titles match by pattern; a title the author trimmed with an ellipsis matches by prefix;
    a step whose title is only known at run time is the last resort.
    """
    squashed = " ".join(title.split())
    for step in steps:
        if not step.dynamic and step.pattern.fullmatch(squashed):
            return step
    trimmed = re.sub(r"\s*(\u2026|\.\.\.)$", "", squashed)
    if trimmed != squashed and trimmed:
        for step in steps:
            if not step.dynamic and (step.title.startswith(trimmed) or step.pattern.match(trimmed)):
                return step
    return next((step for step in steps if step.dynamic), None)
