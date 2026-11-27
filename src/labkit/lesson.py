"""The lesson runtime: labelled steps, visible messages, token totals, run logs, friendly errors.

A lesson script looks like this:

    from labkit import lesson

    @lesson("01.1/1", "Hello, LLM")
    def main(ctx):
        ctx.step("Call the model")
        response = ctx.client.chat.completions.create(model=ctx.model, messages=[...])
        ctx.show_response(response)

    if __name__ == "__main__":
        main()

Flags every lesson accepts:  --raw  (print the HTTP request and response bodies).
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.rule import Rule

from labkit.client import get_async_client, get_client
from labkit.config import Settings, load_settings, repo_root, state_dir, use_utf8_output
from labkit.errors import EXIT_FAILED, explain

ROLE_STYLE = {"system": "magenta", "user": "cyan", "assistant": "green", "tool": "yellow", "developer": "magenta"}


def _plain(value: Any) -> Any:
    """Convert SDK objects into plain data for printing and logging."""
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


class Lesson:
    """Handed to every lesson as `ctx`."""

    def __init__(self, lesson_id: str, title: str, *, raw: bool = False, console: Console | None = None):
        self.id = lesson_id
        self.title = title
        self.raw = raw
        self.console = console or Console(highlight=False, soft_wrap=True)
        self._settings: Settings | None = None
        self._client = None
        self._async_client = None
        self._step = 0
        self._calls = 0
        self._tokens_in = 0
        self._tokens_out = 0
        self._unreported = 0
        self._started = time.perf_counter()
        self._log_path: Path | None = None
        self._log_file = None

    # --- configuration and client -------------------------------------------------

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = load_settings()
        return self._settings

    @property
    def model(self) -> str:
        """The chat model named by LLM_MODEL in .env."""
        return self.settings.require().model

    @property
    def client(self):
        """A ready `openai.OpenAI` client pointed at LLM_BASE_URL."""
        if self._client is None:
            self._client = get_client(self.settings, on_wire=self._on_wire)
        return self._client

    @property
    def async_client(self):
        """The asyncio form of the client (`openai.AsyncOpenAI`), for concurrent calls."""
        if self._async_client is None:
            self._async_client = get_async_client(self.settings, on_wire=self._on_wire)
        return self._async_client

    # --- output -------------------------------------------------------------------

    def step(self, title: str) -> None:
        """Print a numbered heading so the audience can follow the flow."""
        self._step += 1
        self.console.print()
        self.console.print(Rule(f"[bold]Step {self._step}: {escape(title)}[/bold]", align="left", style="blue"))
        self._log("step", number=self._step, title=title)

    def note(self, text: str) -> None:
        """Print a line of commentary."""
        self.console.print(f"[dim]{escape(text)}[/dim]")

    def show_messages(self, messages: Iterable[dict], label: str = "Messages sent to the model") -> None:
        """Print the messages exactly as they will be sent."""
        messages = [_plain(m) for m in messages]
        self.console.print(f"[bold]{escape(label)}[/bold]")
        for message in messages:
            self._print_message(message)
        self._log("messages", messages=messages)

    def show_response(self, response: Any) -> str:
        """Print a chat completion: the reply, any tool calls, and the tokens it used."""
        choice = response.choices[0]
        message = _plain(choice.message)
        self.console.print("[bold]Reply from the model[/bold]")
        self._print_message(message)
        self.console.print(f"[dim]finish_reason: {choice.finish_reason}[/dim]")
        self._log("response", message=message, finish_reason=choice.finish_reason)
        self.record_usage(getattr(response, "usage", None))
        return message.get("content") or ""

    def show_stream(self, stream: Iterable[Any]) -> str:
        """Print a streamed reply piece by piece as it arrives; return the full text."""
        self.console.print("[bold]Reply from the model (streaming)[/bold]")
        out = self.console.file
        if not self.raw:
            self.console.print("[green]assistant[/green] | ", end="")
        parts: list[str] = []
        usage = None
        for chunk in stream:
            if self.raw:
                self.console.print(f"[dim]chunk {escape(json.dumps(_plain(chunk), ensure_ascii=False))}[/dim]")
            if getattr(chunk, "usage", None):
                usage = chunk.usage
            for choice in chunk.choices or []:
                piece = getattr(choice.delta, "content", None)
                if piece:
                    parts.append(piece)
                    if not self.raw:
                        out.write(piece)
                        out.flush()
        text = "".join(parts)
        if self.raw:
            self._print_message({"role": "assistant", "content": text})
        else:
            out.write("\n")
            out.flush()
        self._log("response", message={"role": "assistant", "content": text}, streamed=True)
        self.record_usage(usage)
        return text

    def show_tool_call(self, name: str, arguments: Any, result: Any) -> None:
        """Print one tool call: what the model asked for and what the tool returned."""
        self.console.print(f"[yellow]tool call[/yellow] | {escape(name)}({escape(json.dumps(_plain(arguments), ensure_ascii=False))})")
        self.console.print(f"[yellow]   result[/yellow] | {escape(str(result))}")
        self._log("tool_call", name=name, arguments=_plain(arguments), result=str(result))

    def show_data(self, label: str, data: Any) -> None:
        """Print any structure as indented JSON."""
        self.console.print(f"[bold]{escape(label)}[/bold]")
        self.console.print(escape(json.dumps(_plain(data), indent=2, ensure_ascii=False, default=str)))

    def record_usage(self, usage: Any, *, quiet: bool = False) -> None:
        """Add one model call to the totals and print its token counts.

        Call this yourself when you handle a response without `show_response` / `show_stream`
        (pass `response.usage`). `quiet=True` counts the call without printing a line.
        """
        self._calls += 1
        if isinstance(usage, dict):
            tokens_in, tokens_out = usage.get("prompt_tokens"), usage.get("completion_tokens")
        else:
            tokens_in = getattr(usage, "prompt_tokens", None)
            tokens_out = getattr(usage, "completion_tokens", None)
        if tokens_in is None or tokens_out is None:
            self._unreported += 1
            if not quiet:
                self.console.print("[dim]tokens: not reported by this endpoint[/dim]")
            self._log("usage", reported=False)
            return
        self._tokens_in += tokens_in
        self._tokens_out += tokens_out
        if not quiet:
            self.console.print(f"[dim]tokens: {tokens_in} in + {tokens_out} out = {tokens_in + tokens_out}[/dim]")
        self._log("usage", reported=True, tokens_in=tokens_in, tokens_out=tokens_out)

    # --- internals ----------------------------------------------------------------

    def _print_message(self, message: dict) -> None:
        role = str(message.get("role", "?"))
        style = ROLE_STYLE.get(role, "white")
        content = message.get("content")
        if content:
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            lines = text.splitlines() or [""]
            self.console.print(f"[{style}]{role:>9}[/{style}] | {escape(lines[0])}")
            for line in lines[1:]:
                self.console.print(f"{'':>9} | {escape(line)}")
        for call in message.get("tool_calls") or []:
            fn = call.get("function", {})
            self.console.print(f"[{style}]{role:>9}[/{style}] | [yellow]wants tool[/yellow] {escape(str(fn.get('name')))}({escape(str(fn.get('arguments')))})")
        if not content and not message.get("tool_calls"):
            self.console.print(f"[{style}]{role:>9}[/{style}] | [dim](empty)[/dim]")

    def _on_wire(self, direction: str, summary: str, body: object) -> None:
        self._log("wire", direction=direction, summary=summary, body=body)
        if self.raw:
            arrow = ">>> HTTP request" if direction == "request" else "<<< HTTP response"
            text = body if isinstance(body, str) else json.dumps(body, indent=2, ensure_ascii=False)
            self.console.print(Panel(escape(text), title=f"{arrow}: {escape(summary)}", title_align="left", border_style="dim"))

    def _log(self, event: str, **data: Any) -> None:
        try:
            if self._log_file is None:
                folder = state_dir("logs")
                folder.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                safe_id = self.id.replace("/", "-")
                self._log_path = folder / f"{stamp}-{safe_id}.jsonl"
                self._log_file = self._log_path.open("a", encoding="utf-8")
            record = {"t": round(time.perf_counter() - self._started, 3), "event": event, **data}
            self._log_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            self._log_file.flush()
        except OSError:
            pass  # a read-only folder must never break a lesson

    def _summary(self) -> None:
        elapsed = time.perf_counter() - self._started
        if self._calls == 0:
            tokens = "no model calls"
        elif self._unreported == self._calls:
            tokens = f"{self._calls} model call(s), tokens not reported by this endpoint"
        else:
            total = self._tokens_in + self._tokens_out
            tokens = f"{self._calls} model call(s), {self._tokens_in} in + {self._tokens_out} out = {total} tokens"
            if self._unreported:
                tokens += f" ({self._unreported} call(s) unreported)"
        self.console.print()
        self.console.print(Rule(style="blue"))
        self.console.print(f"[bold]Run summary:[/bold] {tokens}, {elapsed:.1f}s")
        if self._log_path:
            try:
                shown = self._log_path.relative_to(repo_root())
            except ValueError:
                shown = self._log_path
            self.console.print(f"[dim]Log: {shown.as_posix()}[/dim]")
        self._log("summary", calls=self._calls, tokens_in=self._tokens_in, tokens_out=self._tokens_out, seconds=round(elapsed, 2))

    def _run(self, fn: Callable[["Lesson"], Any]) -> int:
        self.console.print(Rule(f"[bold]{escape(self.id)}  {escape(self.title)}[/bold]", style="blue"))
        self._log("start", lesson=self.id, title=self.title, raw=self.raw)
        code = 0
        try:
            if inspect.iscoroutinefunction(fn):
                asyncio.run(fn(self))  # lessons may be written as `async def main(ctx)`
            else:
                fn(self)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Stopped.[/yellow]")
            code = 130
        except Exception as exc:  # noqa: BLE001 - a lesson must never end in a bare stack trace
            code = self._report(exc)
        self._summary()
        if self._log_file:
            self._log_file.close()
        return code

    def _report(self, exc: Exception) -> int:
        explained = explain(exc, self._settings)
        self._log("error", type=type(exc).__name__, message=str(exc), kind=explained.kind if explained else "unexpected")
        self.console.print()
        if explained:
            body = "\n".join(f"- {escape(fix)}" for fix in explained.fixes)
            self.console.print(Panel(body, title=f"[bold red]{escape(explained.title)}[/bold red]", title_align="left", border_style="red"))
            code = explained.exit_code
        else:
            body = f"{type(exc).__name__}: {escape(str(exc))}\n\n- Run again with --raw to see the full technical detail."
            self.console.print(Panel(body, title="[bold red]The lesson stopped on an unexpected error.[/bold red]", title_align="left", border_style="red"))
            code = EXIT_FAILED
        if self.raw:
            self.console.print(escape("".join(traceback.format_exception(exc))), style="dim")
        return code


def lesson(lesson_id: str, title: str) -> Callable[[Callable[[Lesson], Any]], Callable[..., None]]:
    """Wrap a lesson's main(ctx) so it runs with the lesson runtime."""

    def decorator(fn: Callable[[Lesson], Any]) -> Callable[..., None]:
        @functools.wraps(fn)
        def runner(argv: list[str] | None = None) -> None:
            use_utf8_output()
            args = sys.argv[1:] if argv is None else argv
            if "-h" in args or "--help" in args:
                print(f"{lesson_id}  {title}\n\nOptions:\n  --raw   also print each HTTP request and response body")
                return
            code = Lesson(lesson_id, title, raw="--raw" in args)._run(fn)
            if code:
                raise SystemExit(code)

        return runner

    return decorator
