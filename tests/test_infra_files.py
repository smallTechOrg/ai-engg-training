"""Compose files, Dockerfiles and workflow exports cannot be run on every machine (or in CI), so
their structure and safety are checked here instead."""

import json
import re

import pytest
import yaml

from labkit.config import repo_root

MODULES = repo_root() / "modules"
COMPOSE = sorted([*MODULES.rglob("docker-compose.yml"), *MODULES.rglob("compose.yaml")])
DOCKERFILES = sorted(MODULES.rglob("Dockerfile"))
WORKFLOWS = sorted(MODULES.rglob("*workflow*.json"))
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)", re.I)


def rel(path):
    return path.relative_to(repo_root()).as_posix()


@pytest.mark.parametrize("path", COMPOSE, ids=[rel(p) for p in COMPOSE])
def test_compose_file_is_sound(path):
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    services = data.get("services") or {}
    assert services, "no services defined"
    for name, service in services.items():
        assert service.get("image") or service.get("build"), f"{name}: needs an image or a build"
        image = service.get("image", "")
        if image:
            assert not image.endswith(":latest") and ":" in image.split("/")[-1], f"{name}: pin the image tag ({image})"
        for port in service.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name}: bind ports to 127.0.0.1 ({port})"
        environment = service.get("environment", {})
        pairs = environment.items() if isinstance(environment, dict) else [(item.split("=", 1) + [""])[:2] for item in environment]
        for key, value in pairs:
            literal = str(value or "").strip()
            if SECRET_NAME.search(str(key)) and literal and not literal.startswith("${"):
                raise AssertionError(f"{name}: {key} must come from the environment, not be written in the file")


@pytest.mark.parametrize("path", DOCKERFILES, ids=[rel(p) for p in DOCKERFILES])
def test_dockerfile_follows_the_basics(path):
    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    froms = [line for line in lines if line.upper().startswith("FROM ")]
    assert froms and all(":latest" not in line and ":" in line.split()[1] for line in froms if "AS" not in line.upper().split()[1:2] or True), "pin base images"
    assert any(line.upper().startswith("USER ") for line in lines), "run as a non-root user"
    assert any(line.upper().startswith("HEALTHCHECK ") for line in lines), "define a HEALTHCHECK"
    assert not any(re.match(r"(ENV|ARG)\s+\w*(KEY|TOKEN|SECRET|PASSWORD)\w*\s*=?\s*\S+", line, re.I) for line in lines), "no secrets in the image"


@pytest.mark.parametrize("path", WORKFLOWS, ids=[rel(p) for p in WORKFLOWS])
def test_n8n_workflow_export_is_consistent(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    names = {node["name"] for node in data["nodes"]}
    assert len(names) == len(data["nodes"]), "node names must be unique"
    for source, outputs in data["connections"].items():
        assert source in names
        for branch in outputs.get("main", []):
            for link in branch:
                assert link["node"] in names, f"{source} connects to a missing node {link['node']}"
    text = path.read_text(encoding="utf-8")
    assert not re.search(r"(\bsk-[A-Za-z0-9]{16,}|\blsv2_[A-Za-z0-9]{8,}|Bearer\s+[A-Za-z0-9]{12,})", text), "no keys in an exported workflow"
