"""External services the infrastructure lessons use (Redis, Jaeger, Prometheus, Grafana, n8n, Docker).

Every service is addressed by a setting in `.env`, so the same lesson works against a
container on this machine, a native install or a cloud instance. Nothing here is required:
a lesson that needs a service stops cleanly and says how to start it.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse

from labkit.config import load_settings
from labkit.errors import ServiceUnavailable


@dataclass(frozen=True)
class Service:
    env: str  # setting name; for the Docker engine, the pseudo-setting "DOCKER"
    name: str
    example: str  # what to put in .env
    start: str  # how to start one on this machine
    kind: str = "tcp"  # tcp | key | docker


SERVICES: dict[str, Service] = {
    s.env: s
    for s in (
        Service("DOCKER", "Docker", "", "Install Docker Desktop (macOS, Windows) or Docker Engine (Linux): https://docs.docker.com/get-docker/", "docker"),
        Service("REDIS_URL", "Redis", "redis://localhost:6379/0", "docker run --rm -p 6379:6379 redis:7"),
        Service("OTEL_EXPORTER_OTLP_ENDPOINT", "OpenTelemetry collector / Jaeger", "http://localhost:4318", "docker run --rm -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one:latest   (UI: http://localhost:16686)"),
        Service("PROMETHEUS_URL", "Prometheus", "http://localhost:9090", "docker run --rm -p 9090:9090 prom/prometheus"),
        Service("GRAFANA_URL", "Grafana", "http://localhost:3000", "docker run --rm -p 3000:3000 grafana/grafana"),
        Service("N8N_URL", "n8n", "http://localhost:5678", "docker run --rm -p 5678:5678 docker.n8n.io/n8nio/n8n"),
        Service("LANGSMITH_API_KEY", "LangSmith", "lsv2_...", "Create a free key at https://smith.langchain.com (cloud service, optional)", "key"),
    )
}


def _value(env: str) -> str:
    load_settings()  # makes sure .env has been loaded into the environment
    return os.environ.get(env, "").strip()


def _host_port(url: str) -> tuple[str, int] | None:
    parsed = urlparse(url if "://" in url else f"//{url}")
    host = parsed.hostname
    if not host:
        return None
    default = {"redis": 6379, "rediss": 6379, "https": 443, "http": 80}.get(parsed.scheme, 80)
    return host, parsed.port or default


def probe(service: Service, timeout: float = 1.5) -> tuple[str, str]:
    """Return (state, detail). state is one of: unset, ok, down."""
    if service.kind == "docker":
        exe = shutil.which("docker")
        if not exe:
            return "unset", "the docker command was not found"
        try:
            done = subprocess.run([exe, "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.TimeoutExpired):
            return "down", "docker is installed but did not answer"
        if done.returncode != 0:
            return "down", "docker is installed but its engine is not running"
        return "ok", f"engine {done.stdout.strip() or 'running'}"
    value = _value(service.env)
    if not value:
        return "unset", f"{service.env} is not set"
    if service.kind == "key":
        return "ok", f"{service.env} is set"
    target = _host_port(value)
    if target is None:
        return "down", f"{service.env}={value} is not a valid address"
    try:
        with socket.create_connection(target, timeout=timeout):
            return "ok", f"{target[0]}:{target[1]} accepts connections"
    except OSError:
        return "down", f"nothing is listening on {target[0]}:{target[1]}"


def require(env: str, *, how_to_start: str | None = None) -> str:
    """Return the service's setting, or stop the lesson cleanly if it is missing or down.

    Call this at the top of a lesson that needs the service:  url = require("REDIS_URL")
    """
    service = SERVICES[env]
    state, detail = probe(service)
    if state == "ok":
        return "" if service.kind == "docker" else _value(env)
    start = how_to_start or service.start
    if service.kind == "docker":
        fixes = [start, "Then run this lesson again. (Lessons that do not need Docker still run without it.)"]
        raise ServiceUnavailable(f"This lesson needs Docker: {detail}.", fixes)
    if state == "unset":
        fixes = [f"Start one: {start}", f"Then set it in .env, for example {service.env}={service.example}"] if service.example else [start]
    else:
        fixes = [f"Start it: {start}", f"Or point {service.env} in .env at one that is running ({detail})."]
    raise ServiceUnavailable(f"This lesson needs {service.name}: {detail}.", fixes)
