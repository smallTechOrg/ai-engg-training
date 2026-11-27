"""The launcher: `./run` (menu), `./run list`, `./run 01.1`, `./run doctor`, `./run map`."""

from __future__ import annotations

import json
import subprocess
import sys

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from labkit import doctor
from labkit.catalog import LessonInfo, ModuleInfo, find_lesson, find_module, load_catalog, looks_like_target, render_map, scenario, sync_module_readme
from labkit.config import repo_root, state_dir, use_utf8_output
from labkit.errors import EXIT_FAILED, EXIT_SKIPPED

console = Console(highlight=False, soft_wrap=True)
STATUS_STYLE = {"ready": "green", "draft": "yellow", "planned": "dim"}

HELP = """[bold]AI engineering training: launcher[/bold]

  run                 pick a module and lesson from a menu
  run list            every module and lesson, with status
  run 01.1            run all scripts of lesson 01.1, in order
  run 01.1/2          run only the second script of lesson 01.1
  run 01.1 --raw      also show the HTTP requests and responses
  run next            run the lesson after the last one you ran
  run doctor          check your setup    (--report writes a file to send, --offline skips the endpoint)
  run map             regenerate CURRICULUM.md from curriculum.toml
  run check           run every ready lesson against YOUR endpoint and report pass/fail/skip
                      (before a cohort: --module 04, --lesson 04.1, --report writes check-report.txt)

After a lesson finishes, press Enter to go straight to the next one.
On macOS/Linux type ./run, on Windows type run."""


def needs_text(item: LessonInfo, cache: dict | None) -> str:
    """Whether the model can do what a lesson needs, according to the last doctor run."""
    if not item.runnable:
        return ""
    if not item.needs:
        return "[green]ok[/green]"
    if not cache or cache.get("offline"):
        return "[dim]? run doctor[/dim]"
    capabilities = cache.get("capabilities", {})
    missing = [need for need in item.needs if capabilities.get(need) is False]
    unknown = [need for need in item.needs if capabilities.get(need) is None]
    if missing:
        return f"[red]model lacks: {', '.join(missing)}[/red]"
    if unknown:
        return f"[dim]? unchecked: {', '.join(unknown)}[/dim]"
    return "[green]ok[/green]"


def cmd_list(modules: list[ModuleInfo]) -> int:
    cache = doctor.load_cache()
    table = Table(show_lines=False, header_style="bold", box=None, pad_edge=False)
    for column in ("Id", "Title", "Status", "Your setup"):
        table.add_column(column)
    for module in modules:
        table.add_row(f"[bold]{module.id}[/bold]", f"[bold]{escape(module.title)}[/bold]", f"[dim]{module.count('ready')}/{len(module.lessons)} ready[/dim]", "")
        for item in module.lessons:
            style = STATUS_STYLE[item.status]
            table.add_row(f"  {item.id}", f"  {escape(item.title)}", f"[{style}]{item.status}[/{style}]", needs_text(item, cache))
    console.print(table)
    ready = sum(module.count("ready") for module in modules)
    console.print(f"\n{ready} lesson(s) ready. Run one with its id, for example: ./run 01.1")
    return 0


PROGRESS = "progress.json"


def interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def save_progress(item: LessonInfo) -> None:
    try:
        path = state_dir(".labkit") / PROGRESS
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"last_lesson": item.id}), encoding="utf-8")
    except OSError:
        pass


def last_lesson_id() -> str | None:
    try:
        return json.loads((state_dir(".labkit") / PROGRESS).read_text(encoding="utf-8")).get("last_lesson")
    except (OSError, ValueError):
        return None


def next_lesson(modules: list[ModuleInfo], current: LessonInfo | None) -> LessonInfo | None:
    """The next runnable lesson after `current` in course order (the first one if None)."""
    ordered = [item for module in modules for item in module.lessons]
    start = 0
    if current is not None:
        ids = [item.id for item in ordered]
        start = ids.index(current.id) + 1 if current.id in ids else 0
    return next((item for item in ordered[start:] if item.runnable), None)


def offer_next(modules: list[ModuleInfo], item: LessonInfo) -> LessonInfo | None:
    """Ask whether to continue to the next ready lesson. Returns it, or None to stop."""
    upcoming = next_lesson(modules, item)
    if upcoming is None:
        console.print("\n[green]That was the last ready lesson.[/green] See what is coming in CURRICULUM.md.")
        return None
    if not interactive():
        console.print(f"\n[dim]Next: ./run {upcoming.id}  ({escape(upcoming.title)})[/dim]")
        return None
    crossing = "" if upcoming.module.id == item.module.id else f" [dim](module {upcoming.module.id}: {escape(upcoming.module.title)})[/dim]"
    console.print(f"\n[bold]Next lesson:[/bold] {upcoming.id}  {escape(upcoming.title)}{crossing}")
    try:
        answer = input("Press Enter to start it, or q to stop: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return None if answer == "q" else upcoming


def run_course(modules: list[ModuleInfo], item: LessonInfo, extra: list[str]) -> int:
    """Run a whole lesson, then keep offering the next one until the learner stops."""
    while item is not None:
        code = run_lesson(item, None, extra)
        if code:
            return code
        item = offer_next(modules, item)
    return 0


def run_lesson(item: LessonInfo, script_number: int | None, extra: list[str]) -> int:
    if not item.runnable:
        console.print(f"[yellow]Lesson {item.id} ({escape(item.title)}) is planned but not written yet.[/yellow]")
        console.print("See CURRICULUM.md for what is ready, or run: ./run list")
        return EXIT_SKIPPED
    scripts = item.scripts()
    if not scripts:
        console.print(f"[red]Lesson {item.id} has no scripts in {item.path}.[/red]")
        return EXIT_FAILED
    if script_number is not None:
        if not 1 <= script_number <= len(scripts):
            console.print(f"[red]Lesson {item.id} has {len(scripts)} script(s); there is no script {script_number}.[/red]")
            return EXIT_FAILED
        scripts = [scripts[script_number - 1]]
    whole = script_number is None
    skipped: list = []
    for index, script in enumerate(scripts):
        if index and interactive():
            try:
                answer = input(f"\nPress Enter for the next script ({script.name}), or q to stop: ").strip().lower()
            except EOFError:
                answer = ""
            if answer == "q":
                return 0
        console.print(f"\n[dim]$ python {script.relative_to(repo_root()).as_posix()} {' '.join(extra)}[/dim]")
        code = subprocess.run([sys.executable, str(script), *extra], cwd=repo_root()).returncode
        if code == EXIT_SKIPPED:  # the script explained a missing service or package and stopped cleanly
            skipped.append(script)
            continue
        if code:
            return code
    if skipped and len(skipped) == len(scripts):
        return EXIT_SKIPPED  # nothing ran: let the caller know
    if skipped:
        names = ", ".join(script.name for script in skipped)
        console.print(f"\n[yellow]Skipped (needs something not set up): {escape(names)}[/yellow] [dim]Check ./run doctor.[/dim]")
    if whole:
        save_progress(item)
    return 0


def cmd_run(modules: list[ModuleInfo], target: str, extra: list[str]) -> int:
    item, script_number = find_lesson(modules, target)
    if item is not None:
        if script_number is None and item.runnable:
            return run_course(modules, item, extra)
        return run_lesson(item, script_number, extra)
    module = find_module(modules, target) if target.isdigit() else None
    if module is not None:
        console.print(f"[bold]Module {module.id}: {escape(module.title)}[/bold]")
        for lesson_item in module.lessons:
            style = STATUS_STYLE[lesson_item.status]
            console.print(f"  {lesson_item.id}  {escape(lesson_item.title)}  [{style}]{lesson_item.status}[/{style}]")
        console.print("\nRun a lesson with its id, for example: ./run " + module.lessons[0].id)
        return 0
    console.print(f"[red]There is no lesson '{escape(target)}'.[/red] See what exists with: ./run list")
    return EXIT_FAILED


def cmd_next(modules: list[ModuleInfo], extra: list[str]) -> int:
    last = last_lesson_id()
    current, _ = find_lesson(modules, last) if last else (None, None)
    upcoming = next_lesson(modules, current)
    if upcoming is None:
        console.print("[green]You have run every ready lesson.[/green] See what is coming in CURRICULUM.md.")
        return 0
    if last:
        console.print(f"[dim]Last lesson you ran: {last}. Continuing with {upcoming.id}.[/dim]")
    else:
        console.print(f"[dim]No lessons run yet. Starting with {upcoming.id}.[/dim]")
    return run_course(modules, upcoming, extra)


CHECK_REPORT = "check-report.txt"
CHECK_TIMEOUT = 300


def _tidy(line: str) -> str:
    """Strip panel borders from a captured message line."""
    import re

    return re.sub(r"[\u2500-\u257f|\s]+$", "", re.sub(r"^[^A-Za-z]+", "", line)).strip()


def _option(args: list[str], name: str) -> str | None:
    for index, arg in enumerate(args):
        if arg == name and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith(name + "="):
            return arg.split("=", 1)[1]
    return None


def cmd_check(modules: list[ModuleInfo], args: list[str]) -> int:
    """Run every ready script for real and summarise. Exit 0 only if nothing failed."""
    import time

    from labkit.catalog import extra_installed

    only_module, only_lesson = _option(args, "--module"), _option(args, "--lesson")
    rows: list[tuple[str, str, str, float, str]] = []  # (status, script id, lesson, seconds, note)
    console.print("[bold]Live check[/bold]: running every ready lesson script against your endpoint.")
    console.print("[dim]This makes real model calls. Scripts that need a missing package or service are skipped, not failed.[/dim]\n")
    for module in modules:
        if only_module and module.id != only_module.zfill(2):
            continue
        for item in module.lessons:
            if not item.runnable or (only_lesson and item.id != only_lesson):
                continue
            missing = [extra for extra in module.extras if extra != "all" and not extra_installed(extra)]
            for number, script in enumerate(item.scripts(), 1):
                script_id = f"{item.id}/{number}"
                if missing:
                    rows.append(("SKIP", script_id, item.title, 0.0, "packages not installed: " + ", ".join(missing)))
                    console.print(f"[dim]SKIP[/dim]  {script_id:8} {escape(item.title)}  [dim](install: {', '.join(missing)})[/dim]")
                    continue
                started = time.perf_counter()
                try:
                    done = subprocess.run([sys.executable, str(script)], cwd=repo_root(), capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=CHECK_TIMEOUT)
                    code, text = done.returncode, done.stdout + done.stderr
                except subprocess.TimeoutExpired:
                    code, text = 124, "timed out"
                seconds = time.perf_counter() - started
                if code == 0:
                    rows.append(("PASS", script_id, item.title, seconds, ""))
                    console.print(f"[green]PASS[/green]  {script_id:8} {escape(item.title)}  [dim]{seconds:.1f}s[/dim]")
                elif code == EXIT_SKIPPED:
                    note = next((_tidy(line) for line in text.splitlines() if "needs" in line.lower()), "needs something not set up")
                    rows.append(("SKIP", script_id, item.title, seconds, note[:100]))
                    console.print(f"[dim]SKIP[/dim]  {script_id:8} {escape(item.title)}  [dim]{escape(note[:90])}[/dim]")
                else:
                    reason = next((_tidy(line) for line in text.splitlines() if "stopped" in line or "rejected" in line or "Could not" in line or "model lacks" in line or "not found" in line), "exit code " + str(code))
                    rows.append(("FAIL", script_id, item.title, seconds, reason[:100]))
                    console.print(f"[red]FAIL[/red]  {script_id:8} {escape(item.title)}  [red]{escape(reason[:90])}[/red]  [dim](re-run: ./run {script_id})[/dim]")
    counts = {name: sum(1 for row in rows if row[0] == name) for name in ("PASS", "FAIL", "SKIP")}
    console.print(f"\n[bold]{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped[/bold] of {len(rows)} scripts.")
    if counts["FAIL"]:
        console.print("[red]Fix the FAIL lines before the cohort. Start with ./run doctor if several fail at once.[/red]")
    if "--report" in args:
        lines = [f"{status:4} {sid:8} {title}  {note}".rstrip() for status, sid, title, _, note in rows]
        (repo_root() / CHECK_REPORT).write_text("\n".join(lines) + "\n", encoding="utf-8")
        console.print(f"[dim]Wrote {CHECK_REPORT} (no secrets).[/dim]")
    return 1 if counts["FAIL"] or not rows else 0


def cmd_map(modules: list[ModuleInfo]) -> int:
    path = repo_root() / "CURRICULUM.md"
    path.write_text(render_map(modules, scenario()), encoding="utf-8", newline="\n")
    console.print(f"Wrote {path.name}")
    for module in modules:
        readme = module.path / "README.md"
        existing = readme.read_text(encoding="utf-8") if readme.is_file() else None
        updated = sync_module_readme(existing, module, scenario())
        if updated != existing:
            module.path.mkdir(parents=True, exist_ok=True)
            readme.write_text(updated, encoding="utf-8", newline="\n")
            console.print(f"Wrote modules/{module.slug}/README.md")
    return 0


def _ask(prompt: str) -> str | None:
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def cmd_menu(modules: list[ModuleInfo]) -> int:
    """Pick by the real ids: module 4 (or 04), then lesson 3 (or 04.3)."""
    if not interactive():
        return cmd_list(modules)
    while True:
        console.print("\n[bold]Modules[/bold]")
        for module in modules:
            ready = module.count("ready")
            style = "green" if ready else "dim"
            console.print(f"  {module.id}  {escape(module.title)}  [{style}]{ready}/{len(module.lessons)} ready[/{style}]")
        last = last_lesson_id()
        hint = f", n for the lesson after {last}" if last else ""
        answer = _ask(f"\nModule number (e.g. 1 or 01){hint}, q to quit: ")
        if answer in (None, "", "q"):
            return 0
        if answer == "n":
            cmd_next(modules, [])
            continue
        if looks_like_target(answer) and "." in answer:
            cmd_run(modules, answer, [])
            continue
        module = find_module(modules, answer) if answer.isdigit() else None
        if module is None:
            console.print(f"[yellow]There is no module '{escape(answer)}'. Type a number from 0 to {int(modules[-1].id)}.[/yellow]")
            continue
        while True:
            console.print(f"\n[bold]{module.id}  {escape(module.title)}[/bold]\n[dim]{escape(module.summary)}[/dim]")
            for item in module.lessons:
                style = STATUS_STYLE[item.status]
                console.print(f"  {item.id}  {escape(item.title)}  [{style}]{item.status}[/{style}]")
            answer = _ask(f"\nLesson number (e.g. 1 or {module.id}.1), Enter to go back: ")
            if answer in (None, "", "b", "q"):
                break
            target = answer if "." in answer else f"{module.id}.{answer}"
            item, script = find_lesson(modules, target) if looks_like_target(target) else (None, None)
            if item is None:
                console.print(f"[yellow]There is no lesson '{escape(answer)}' in module {module.id}.[/yellow]")
                continue
            if script is None and item.runnable:
                run_course(modules, item, [])
            else:
                run_lesson(item, script, [])


def main(argv: list[str] | None = None) -> None:
    use_utf8_output()
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "menu"
    if command in ("-h", "--help", "help"):
        console.print(HELP)
        raise SystemExit(0)
    if command == "doctor":
        raise SystemExit(doctor.main(args[1:], console))
    modules = load_catalog()
    if command == "menu":
        code = cmd_menu(modules)
    elif command == "list":
        code = cmd_list(modules)
    elif command == "map":
        code = cmd_map(modules)
    elif command == "check":
        code = cmd_check(modules, args[1:])
    elif command == "next":
        code = cmd_next(modules, args[1:])
    elif command == "run" and len(args) > 1:
        code = cmd_run(modules, args[1], args[2:])
    elif looks_like_target(command):
        code = cmd_run(modules, command, args[1:])
    else:
        console.print(f"[red]Unknown command '{escape(command)}'.[/red]\n")
        console.print(HELP)
        code = EXIT_FAILED
    raise SystemExit(code)


if __name__ == "__main__":
    main()
