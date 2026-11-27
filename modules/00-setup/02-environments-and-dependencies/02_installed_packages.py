"""00.2/2  What is installed, and why exactly that?

Three files decide which packages you get: pyproject.toml says what the project needs
("openai, version 3 or newer"), uv.lock records the exact versions that were chosen, and
the .venv folder holds what is actually installed. This script reads all three and
compares them. No model calls.

Run it:   ./run 00.2/2          (Windows: run 00.2/2)
"""

import importlib
import tomllib
from importlib import metadata
from pathlib import Path

from labkit import lesson, repo_root

# Distribution name (what you install) -> module name (what you import). They can differ.
PACKAGES = {"openai": "openai", "pydantic": "pydantic", "python-dotenv": "dotenv", "rich": "rich", "labkit": "labkit"}


def installed_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "(not installed)"


def short(path: str, root: Path) -> str:
    """Show a path relative to the repo when possible: shorter and the same on every machine."""
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path


@lesson("00.2/2", "What is installed, and why exactly that?")
def main(ctx):
    root = repo_root()

    ctx.step("What the project asks for: pyproject.toml")
    with (root / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    ctx.show_data("[project] dependencies", project.get("dependencies", []))
    ctx.note("These are ranges ('3.0 or newer'), not exact versions. Ranges alone give different people different installs.")

    ctx.step("What was chosen: uv.lock")
    locked = {}
    lock_file = root / "uv.lock"
    if lock_file.is_file():
        with lock_file.open("rb") as handle:
            locked = {package["name"]: package.get("version", "(local project)") for package in tomllib.load(handle).get("package", [])}
        ctx.note(f"uv.lock pins {len(locked)} packages: the {len(project.get('dependencies', []))} you asked for plus everything they need.")
    else:
        ctx.note("No uv.lock found (you may have installed with pip). Versions are then whatever pip resolved that day.")

    ctx.step("What is actually installed: the environment")
    rows = {}
    drift = []
    for name in PACKAGES:
        have, want = installed_version(name), locked.get(name, "(not in lockfile)")
        rows[name] = {"installed": have, "locked": want}
        if name != "labkit" and want not in ("(not in lockfile)", have):
            drift.append(name)
    ctx.show_data("Installed compared with locked", rows)
    if drift:
        ctx.note("Differs from the lockfile: " + ", ".join(drift) + ". Run the setup script again (or `uv sync`) to match.")
    else:
        ctx.note("Installed versions match the lockfile: you have the same packages as everyone else on this course.")

    ctx.step("Where an import really comes from")
    ctx.note("The name you install and the name you import can differ (python-dotenv is imported as dotenv).")
    origins = {}
    for name, module_name in PACKAGES.items():
        try:
            module = importlib.import_module(module_name)
            origins[f"import {module_name}"] = short(getattr(module, "__file__", "?") or "?", root)
        except ImportError:
            origins[f"import {module_name}"] = "(cannot be imported)"
    ctx.show_data("Module files", origins)
    ctx.note("Third-party packages live in .venv/.../site-packages. labkit is imported from src/ in this repo:")
    ctx.note("it is installed in 'editable' mode, so changes to its source take effect without reinstalling.")


if __name__ == "__main__":
    main()
