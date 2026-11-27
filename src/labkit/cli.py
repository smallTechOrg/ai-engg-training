"""The launcher: `./run` (menu), `./run list`, `./run 01.1`, `./run doctor`, `./run map`."""

from __future__ import annotations

import subprocess
import sys

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from labkit import doctor
from labkit.catalog import LessonInfo, ModuleInfo, find_lesson, find_module, load_catalog, looks_like_target, render_map, scenario, sync_module_readme
from labkit.config import repo_root, use_utf8_output
from labkit.errors import EXIT_FAILED, EXIT_SKIPPED

console = Console(highlight=False, soft_wrap=True)
STATUS_STYLE = {"ready": "green", "draft": "yellow", "planned": "dim"}

HELP = """[bold]AI engineering training: launcher[/bold]

  run                 pick a module and lesson from a menu
  run list            every module and lesson, with status
  run 01.1            run all scripts of lesson 01.1, in order
  run 01.1/2          run only the second script of lesson 01.1
  run 01.1 --raw      also show the HTTP requests and responses
  run doctor          check your setup    (--report writes a file to send, --offline skips the endpoint)
  run map             regenerate CURRICULUM.md from curriculum.toml

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
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    for index, script in enumerate(scripts):
        if index and interactive:
            try:
                answer = input(f"\nPress Enter for the next script ({script.name}), or q to stop: ").strip().lower()
            except EOFError:
                answer = ""
            if answer == "q":
                return 0
        console.print(f"\n[dim]$ python {script.relative_to(repo_root()).as_posix()} {' '.join(extra)}[/dim]")
        code = subprocess.run([sys.executable, str(script), *extra], cwd=repo_root()).returncode
        if code:
            return code
    return 0


def cmd_run(modules: list[ModuleInfo], target: str, extra: list[str]) -> int:
    item, script_number = find_lesson(modules, target)
    if item is not None:
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


def _choose(prompt: str, count: int) -> int | None:
    """Ask for a number between 1 and count. None means back/quit."""
    while True:
        try:
            answer = input(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if answer in ("", "q", "b"):
            return None
        if answer.isdigit() and 1 <= int(answer) <= count:
            return int(answer)
        console.print(f"[yellow]Type a number from 1 to {count}, or q.[/yellow]")


def cmd_menu(modules: list[ModuleInfo]) -> int:
    if not sys.stdin.isatty():
        return cmd_list(modules)
    while True:
        console.print("\n[bold]Modules[/bold]")
        for index, module in enumerate(modules, 1):
            ready = module.count("ready")
            style = "green" if ready else "dim"
            console.print(f"  {index:>2}. {module.id}  {escape(module.title)}  [{style}]{ready}/{len(module.lessons)} ready[/{style}]")
        picked = _choose("\nModule number (q to quit): ", len(modules))
        if picked is None:
            return 0
        module = modules[picked - 1]
        while True:
            console.print(f"\n[bold]{module.id}  {escape(module.title)}[/bold]\n[dim]{escape(module.summary)}[/dim]")
            for index, item in enumerate(module.lessons, 1):
                style = STATUS_STYLE[item.status]
                console.print(f"  {index:>2}. {item.id}  {escape(item.title)}  [{style}]{item.status}[/{style}]")
            picked = _choose("\nLesson number (Enter to go back): ", len(module.lessons))
            if picked is None:
                break
            run_lesson(module.lessons[picked - 1], None, [])


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
