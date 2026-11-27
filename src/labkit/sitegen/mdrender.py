"""Markdown and code rendering for the course site: markdown-it, heading anchors, Pygments."""

from __future__ import annotations

import html
import re

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.anchors import anchors_plugin
from pygments.lexers import TextLexer, get_lexer_by_name, get_lexer_for_filename
from pygments.token import STANDARD_TYPES
from pygments.util import ClassNotFound

COMMAND_LINE = re.compile(r"^(\./run|run |python |\.\\run)")
LEXER_ALIASES = {"sh": "bash", "shell": "bash", "console": "bash", "yml": "yaml", "py": "python", "dockerfile": "docker", "env": "text", "text": "text", "txt": "text", "": "text"}


def _token_class(ttype) -> str:
    while ttype not in STANDARD_TYPES:
        ttype = ttype.parent
    return STANDARD_TYPES[ttype]


def lexer_for(lang: str = "", filename: str = ""):
    name = LEXER_ALIASES.get(lang.lower(), lang.lower())
    try:
        if name and name != "text":
            return get_lexer_by_name(name)
        if filename and not lang:
            base = filename.rsplit("/", 1)[-1]
            if base == "Dockerfile":
                return get_lexer_by_name("docker")
            if base.endswith((".example", ".dockerignore", ".gitignore", ".bad", ".env")):
                return TextLexer()
            return get_lexer_for_filename(base)
    except ClassNotFound:
        pass
    return TextLexer()


def highlight_lines(code: str, lexer) -> str:
    """Highlighted HTML where every source line is one `<span class="line">` (newline inside it).

    Tokens that span lines are split, so spans never cross a line boundary.
    """
    out: list[str] = []
    line: list[str] = []
    for ttype, value in lexer.get_tokens(code.rstrip("\n") + "\n"):
        cls = _token_class(ttype)
        pieces = value.split("\n")
        for index, piece in enumerate(pieces):
            if piece:
                text = html.escape(piece, quote=False)
                line.append(f'<span class="{cls}">{text}</span>' if cls else text)
            if index < len(pieces) - 1:
                out.append('<span class="line">' + "".join(line) + "\n</span>")
                line = []
    if line:
        out.append('<span class="line">' + "".join(line) + "\n</span>")
    return "".join(out)


def plain_lines(code: str) -> str:
    return "".join(f'<span class="line">{html.escape(text, quote=False)}\n</span>' for text in code.rstrip("\n").split("\n"))


def code_block(code: str, lang: str = "", *, filename: str = "", start: int = 1, numbered: bool = True, sha: str = "", label: str = "", highlight: bool = True) -> str:
    """The standard code box: label, copy button, optional line numbers."""
    lexer = lexer_for(lang, filename) if highlight else TextLexer()
    body = highlight_lines(code, lexer) if highlight else plain_lines(code)
    shown = label or (lang if lang and lang != "text" else "")
    attrs = f' data-sha256="{sha}"' if sha else ""
    cls = "codeblock" + ("" if numbered else " nonum")
    style = f' style="counter-reset: ln {start - 1}"' if start != 1 else ""
    bar = f'<span class="lang">{html.escape(shown)}</span>' if shown else '<span class="lang"></span>'
    return (
        f'<div class="{cls}"{attrs}><div class="codebar">{bar}'
        '<button class="copy" type="button" aria-label="Copy code">Copy</button></div>'
        f'<pre tabindex="0"><code{style}>{body}</code></pre></div>'
    )


def terminal_block(text: str, caption: str = "Output") -> str:
    body = "".join(f'<span class="tline">{html.escape(t, quote=False)}\n</span>' for t in text.rstrip("\n").split("\n"))
    return (
        '<div class="terminal"><div class="termbar"><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>'
        f'<span class="termtitle">{html.escape(caption)}</span>'
        '<button class="copy" type="button" aria-label="Copy output">Copy</button></div>'
        f'<pre tabindex="0"><code>{body}</code></pre></div>'
    )


def command_block(command: str) -> str:
    return (
        '<div class="cmd"><code>' + html.escape(command, quote=False) + "</code>"
        '<button class="copy" type="button" aria-label="Copy command">Copy</button></div>'
    )


def make_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True, "typographer": False}).enable("table").enable("strikethrough")
    md.use(anchors_plugin, min_level=2, max_level=4)

    def fence(self, tokens, idx, options, env):
        token = tokens[idx]
        lang = (token.info or "").strip().split(" ")[0]
        code = token.content
        if lang == "mermaid":
            env["mermaid"] = True
            return (
                '<figure class="diagram"><pre class="mermaid" data-diagram-source>'
                + html.escape(code.strip("\n"), quote=False)
                + "</pre></figure>"
            )
        if token.meta.get("terminal"):
            return terminal_block(code, "Expected output")
        lines = code.rstrip("\n").split("\n")
        if not lang and len(lines) <= 2 and all(COMMAND_LINE.match(x) for x in lines):
            return command_block("\n".join(lines))
        if not lang:
            return code_block(code, "", numbered=False, highlight=False)
        return code_block(code, lang, numbered=len(lines) >= 3)

    def heading_close(self, tokens, idx, options, env):
        opener = tokens[idx - 2]
        anchor = opener.attrGet("id")
        link = f'<a class="anchor" href="#{anchor}" aria-label="Link to this section">#</a>' if anchor else ""
        return f"{link}</{tokens[idx].tag}>\n"

    md.add_render_rule("heading_close", heading_close)
    md.add_render_rule("fence", fence)
    md.add_render_rule("table_open", lambda self, tokens, idx, options, env: '<div class="table-wrap"><table>')
    md.add_render_rule("table_close", lambda self, tokens, idx, options, env: "</table></div>")
    return md


def is_output_label(tokens: list[Token], index: int) -> bool:
    """A paragraph starting with **Expected output** directly followed by a fence."""
    if tokens[index].type != "paragraph_open" or index + 3 >= len(tokens):
        return False
    inline = tokens[index + 1]
    return inline.type == "inline" and inline.content.startswith("**Expected output") and tokens[index + 3].type == "fence"


def inline_text(token: Token) -> str:
    """Plain text of an inline token (code spans kept, emphasis marks dropped)."""
    parts = []
    for child in token.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts)
