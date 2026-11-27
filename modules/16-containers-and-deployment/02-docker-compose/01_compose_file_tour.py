"""16.2/1  A tour of the compose file: services, start order and safety checks

Docker Compose describes a whole stack (API, worker, Redis, vector store) in one file. This
script READS the shipped docker-compose.yml and works out what Compose would work out: which
service has to be healthy before which, in what order things start, which ports are exposed,
and whether the file follows the course's safety rules. It never runs Docker.

Run it:   ./run 16.2/1          (Windows: run 16.2/1)
"""

import re
from pathlib import Path

from labkit import lesson

COMPOSE = Path(__file__).with_name("docker-compose.yml")
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)", re.I)


def parse_yaml(text: str):
    """A small YAML reader for the subset compose and workflow files use: maps, lists, quoted
    and plain scalars, one-line [a, b] / {} values and `|` blocks. Real projects use PyYAML."""
    blocks: list[str] = []
    items: list[tuple[int, str]] = []
    raw = text.splitlines()
    i = 0
    while i < len(raw):
        line = raw[i].rstrip()
        i += 1
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()
        if body.endswith((": |", ": >", ": |-", ": >-")):
            parent, text_lines = indent, []
            while i < len(raw) and (not raw[i].strip() or len(raw[i]) - len(raw[i].lstrip()) > parent):
                text_lines.append(raw[i].strip())
                i += 1
            blocks.append("\n".join(text_lines).strip())
            body = body.rsplit(":", 1)[0] + f": @@{len(blocks) - 1}"
        items.append((indent, body))

    def scalar(value: str):
        value = value.strip()
        if value.startswith("@@"):
            return blocks[int(value[2:])]
        if value[:1] == "[" and value[-1:] == "]":
            inner = value[1:-1].strip()
            parts = re.findall(r"""\s*("[^"]*"|'[^']*'|[^,]+)\s*(?:,|$)""", inner)
            return [scalar(part) for part in parts]
        if value == "{}":
            return {}
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            return value[1:-1]
        if value.isdigit():
            return int(value)
        return {"true": True, "false": False}.get(value, value)

    def split_key(body: str):
        found = re.match(r"""^("[^"]*"|'[^']*'|[^\s"'\[{\-][^:]*?):(?:\s+(.*))?$""", body)
        return (found.group(1).strip("\"'"), found.group(2) or "") if found else None

    def parse(pos: int, indent: int):
        if items[pos][1].startswith("- "):
            result = []
            while pos < len(items) and items[pos][0] == indent and items[pos][1].startswith("- "):
                rest = items[pos][1][2:].strip()
                if split_key(rest):
                    items[pos] = (indent + 2, rest)
                    value, pos = parse(pos, indent + 2)
                else:
                    value, pos = scalar(rest), pos + 1
                result.append(value)
            return result, pos
        result = {}
        while pos < len(items) and items[pos][0] == indent and not items[pos][1].startswith("- "):
            key, value = split_key(items[pos][1]) or (items[pos][1], "")
            pos += 1
            if value:
                result[key] = scalar(value)
            elif pos < len(items) and (items[pos][0] > indent or (items[pos][0] == indent and items[pos][1].startswith("- "))):
                result[key], pos = parse(pos, items[pos][0])
            else:
                result[key] = None
        return result, pos

    return parse(0, items[0][0])[0] if items else {}


def start_order(services: dict) -> list[list[str]]:
    """Group services into waves: a service starts once everything it depends_on has started."""
    needs = {}
    for name, svc in services.items():
        dep = svc.get("depends_on") or {}
        needs[name] = set(dep if isinstance(dep, list) else dep.keys())
    waves, done = [], set()
    while len(done) < len(needs):
        wave = sorted(n for n in needs if n not in done and needs[n] <= done)
        if not wave:
            raise ValueError("circular depends_on")
        waves.append(wave)
        done |= set(wave)
    return waves


def problems(services: dict) -> list[str]:
    found = []
    for name, svc in services.items():
        image = svc.get("image", "")
        if image and (":" not in image.split("/")[-1] or image.endswith(":latest")):
            found.append(f"{name}: image {image!r} is not pinned to a tag")
        for port in svc.get("ports", []):
            if not str(port).startswith("127.0.0.1:"):
                found.append(f"{name}: port {port} is open to the network (bind to 127.0.0.1)")
        for key, value in (svc.get("environment") or {}).items():
            if SECRET_NAME.search(key) and value and not str(value).startswith("${"):
                found.append(f"{name}: {key} is written in the file")
        if "restart" not in svc:
            found.append(f"{name}: no restart policy")
        if "healthcheck" not in svc and name not in {"chroma"}:
            found.append(f"{name}: no healthcheck")
    return found


@lesson("16.2/1", "A tour of the compose file")
def main(ctx):
    data = parse_yaml(COMPOSE.read_text(encoding="utf-8"))
    services = data["services"]

    ctx.step("The services in docker-compose.yml")
    for name, svc in services.items():
        source = svc.get("image") if "image" in svc and "build" not in svc else f"built from {svc['build']!r} -> {svc.get('image', '')}"
        command = " ".join(svc["command"]) if "command" in svc else "(image default)"
        print(f"  {name:<7} {source}")
        print(f"          command: {command}")
        print(f"          ports: {svc.get('ports', 'none (reachable only inside the stack)')}")
    print("  named volumes:", ", ".join(data.get("volumes", {})))

    ctx.step("How the containers find each other")
    ctx.note("Compose puts every service on one private network and makes each service name a DNS name.")
    for name, svc in services.items():
        for key, value in (svc.get("environment") or {}).items():
            if "://" in str(value):
                print(f"  {name}: {key}={value}   <- 'redis' and 'chroma' here are SERVICE NAMES, not localhost")

    ctx.step("Start order from depends_on and healthchecks")
    for number, wave in enumerate(start_order(services), 1):
        notes = []
        for name in wave:
            for dep, cfg in (services[name].get("depends_on") or {}).items():
                notes.append(f"{name} waits for {dep} ({cfg['condition']})")
        print(f"  wave {number}: {', '.join(wave)}" + (f"   [{'; '.join(notes)}]" if notes else ""))
    ctx.note("service_started only waits for the process to exist; service_healthy waits for its healthcheck to pass.")

    ctx.step("Safety and operations checks")
    found = problems(services)
    print("  all checks pass" if not found else "\n".join(f"  FAIL {item}" for item in found))
    print("  secrets: LLM_API_KEY is not in this file; it arrives through env_file: .env")

    ctx.step("The same checks on a careless file (embedded)")
    careless = parse_yaml(
        "services:\n  db:\n    image: redis:latest\n    ports:\n      - \"6379:6379\"\n"
        "  api:\n    image: myapp:1\n    environment:\n      OPENAI_API_KEY: sk-abc\n"
    )["services"]
    for item in problems(careless):
        print(f"  FAIL {item}")

    ctx.step("Commands for you to run (this script never runs them)")
    print("  cp .env.example .env && docker compose up --build -d")
    print("  docker compose ps            # healthy, healthy, healthy, running")
    print("  docker compose logs -f worker")
    print("  docker compose down          # add -v to also delete the redis and chroma volumes")


if __name__ == "__main__":
    main()
