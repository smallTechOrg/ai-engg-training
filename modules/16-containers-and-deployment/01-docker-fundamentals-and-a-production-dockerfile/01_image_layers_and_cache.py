"""16.1/1  Images, layers and the build cache, by reading a Dockerfile

An image is a stack of layers; each Dockerfile instruction that changes the filesystem makes
one. Docker reuses a cached layer only if the instruction AND everything below it are unchanged.
This script parses the shipped Dockerfile and SIMULATES that rule. It is a teaching model:
it does not run Docker and ignores details such as BuildKit parallelism and cache mounts.

Run it:   ./run 16.1/1          (Windows: run 16.1/1)
"""

from pathlib import Path

from labkit import lesson

DOCKERFILE = Path(__file__).parent / "Dockerfile"
LAYER_MAKERS = {"RUN", "COPY", "ADD"}  # these create filesystem layers; the rest are metadata


def parse(text: str) -> list[tuple[str, str]]:
    """Return (INSTRUCTION, arguments) pairs, joining backslash continuations, skipping comments."""
    out, buf = [], ""
    for raw in text.splitlines():
        line = raw.strip()
        if not buf and (not line or line.startswith("#")):
            continue
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        buf += line
        word, _, rest = buf.partition(" ")
        out.append((word.upper(), rest.strip()))
        buf = ""
    return out


def inputs_of(instr: str, args: str) -> set[str]:
    """What files an instruction depends on (COPY sources); RUN depends on the layers above."""
    if instr in {"COPY", "ADD"}:
        parts = [p for p in args.split() if not p.startswith("--")]
        return {p.rstrip("/") for p in parts[:-1]}
    return set()


def rebuilt(steps: list[tuple[str, str]], changed: str) -> list[bool]:
    """Everything from the first instruction touching `changed` downwards is rebuilt (per stage)."""
    result, busted = [], False
    for instr, args in steps:
        if instr == "FROM":
            busted = False
        if instr in {"COPY", "ADD"} and any(s == changed or s.startswith(changed + "/") or changed.startswith(s + "/") for s in inputs_of(instr, args)):
            busted = True
        result.append(busted)
    return result


@lesson("16.1/1", "Images, layers and the build cache")
def main(ctx):
    steps = parse(DOCKERFILE.read_text(encoding="utf-8"))

    ctx.step("Each instruction, as a layer")
    ctx.note("Instructions that change files (RUN, COPY, ADD) add a layer; the others only add metadata.")
    for n, (instr, args) in enumerate(steps, 1):
        kind = "layer   " if instr in LAYER_MAKERS else "metadata" if instr != "FROM" else "base    "
        print(f"{n:2}. [{kind}] {instr:<11} {args[:70]}")

    ctx.step("Cache-busting order check")
    ctx.note("A COPY of the whole app BEFORE the dependency install means every code edit reinstalls everything.")
    problems, copied_all = [], False
    for instr, args in steps:
        if instr == "FROM":
            copied_all = False
        if instr in {"COPY", "ADD"} and any(s in {".", "./"} for s in inputs_of(instr, args)):
            copied_all = True
        if instr == "RUN" and ("sync" in args or "pip install" in args) and copied_all:
            problems.append(f"dependency install after COPY . : {args[:50]}")
    print("Order problems found:" if problems else "No order problems: dependency files are copied before the code.")
    for p in problems:
        print("  -", p)

    ctx.step("Simulation: what rebuilds when you change something")
    ctx.note("SIMULATION from the Dockerfile text, not a real build. Stage-by-stage, top to bottom.")
    for changed, label in (("app/main.py", "edit one line of code"), ("pyproject.toml", "change a dependency")):
        flags = rebuilt(steps, changed)
        layers = [(i, s) for i, (s, f) in enumerate(zip(steps, flags)) if s[0] in LAYER_MAKERS]
        redo = [f"{s[0]} {s[1][:38]}" for i, s in layers if flags[i]]
        cached = len(layers) - len(redo)
        print(f"\nYou {label} ({changed}): {cached} layer(s) cached, {len(redo)} rebuilt")
        for r in redo:
            print("   rebuilt:", r)
    ctx.note("Cached layers build in about a second; the dependency layer is the slow one. Keep it cached.")


if __name__ == "__main__":
    main()
