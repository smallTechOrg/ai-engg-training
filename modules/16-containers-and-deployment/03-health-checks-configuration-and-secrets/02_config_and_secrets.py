"""16.3/2  Configuration and secrets: the twelve-factor way, with Docker secrets

The same image must run on your laptop, in CI and in production, so everything that differs is
configuration, read at start-up from the environment. Secrets are configuration too, but they must
not appear in `docker inspect`, in logs or in the image. Docker secrets and Kubernetes secrets mount
a secret as a FILE (for example /run/secrets/llm_api_key); apps then read `LLM_API_KEY_FILE`.

This script builds a settings loader with that rule and the precedence rules, validates everything at
start-up (fail fast, all problems at once), and masks secrets when printing. It uses temporary
files, a fake key and no model.

Run it:   ./run 16.3/2          (Windows: run 16.3/2)
"""

import tempfile
from pathlib import Path

from pydantic import BaseModel, ValidationError, field_validator

from labkit import lesson

SECRET_FIELDS = {"llm_api_key"}


class Settings(BaseModel):
    llm_base_url: str
    llm_model: str
    llm_api_key: str
    redis_url: str = "redis://redis:6379/0"
    log_level: str = "info"
    worker_concurrency: int = 2

    @field_validator("llm_base_url")
    @classmethod
    def must_be_http(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("must start with http:// or https://")
        return value

    @field_validator("worker_concurrency")
    @classmethod
    def sane_concurrency(cls, value: int) -> int:
        if not 1 <= value <= 32:
            raise ValueError("must be between 1 and 32")
        return value

    def masked(self) -> dict:
        data = self.model_dump()
        for name in SECRET_FIELDS:
            data[name] = f"{data[name][:3]}... ({len(data[name])} chars)" if data[name] else ""
        return data


def read_env_file(path: Path) -> dict[str, str]:
    """A .env file: KEY=value lines, # comments. Lowest precedence after the defaults."""
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


def load_settings(environ: dict[str, str], env_file: Path | None = None) -> Settings:
    """defaults (in the class) < .env file < real environment variables < NAME_FILE secret files."""
    merged = {**(read_env_file(env_file) if env_file else {}), **environ}
    raw = {}
    for field in Settings.model_fields:
        name = field.upper()
        if f"{name}_FILE" in merged:  # secret mounted as a file: the file wins
            raw[field] = Path(merged[f"{name}_FILE"]).read_text(encoding="utf-8").strip()
        elif name in merged:
            raw[field] = merged[name]
    return Settings(**raw)


def report(label: str, build) -> Settings | None:
    try:
        settings = build()
    except (ValidationError, OSError) as exc:
        print(f"  {label}: REFUSING TO START")
        if isinstance(exc, ValidationError):
            for error in exc.errors():
                print(f"     - {'.'.join(str(p).upper() for p in error['loc'])}: {error['msg']}")
        else:
            print(f"     - {type(exc).__name__}: secret file could not be read")
        return None
    print(f"  {label}: ok -> {settings.masked()}")
    return settings


@lesson("16.3/2", "Configuration and secrets")
def main(ctx):
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        env_file = folder / ".env"
        env_file.write_text("# local development values\nLLM_BASE_URL=http://localhost:11434/v1\nLLM_MODEL=dev-model\nLLM_API_KEY=sk-demo-from-env-file\nLOG_LEVEL=debug\n", encoding="utf-8")
        secret = folder / "llm_api_key"
        secret.write_text("sk-demo-from-secret-file\n", encoding="utf-8")

        ctx.step("Precedence: defaults < .env file < environment < secret file")
        report("only the .env file", lambda: load_settings({}, env_file))
        report("env var overrides the file", lambda: load_settings({"LLM_MODEL": "prod-model", "LOG_LEVEL": "info"}, env_file))
        report("secret file overrides both", lambda: load_settings({"LLM_API_KEY_FILE": str(secret)}, env_file))
        ctx.note("Defaults live in code, per-machine values in .env, per-deployment values in real environment variables.")

        ctx.step("Fail fast: bad or missing settings stop the app at start-up, with every problem listed")
        report("nothing configured", lambda: load_settings({}))
        report("typos and bad values", lambda: load_settings({"LLM_BASE_URL": "localhost:11434", "LLM_MODEL": "m", "LLM_API_KEY": "k", "WORKER_CONCURRENCY": "500"}))
        report("secret file missing", lambda: load_settings({"LLM_BASE_URL": "http://x", "LLM_MODEL": "m", "LLM_API_KEY_FILE": str(folder / "nope")}))

        ctx.step("Never print a secret: the masked view")
        settings = load_settings({"LLM_API_KEY_FILE": str(secret)}, env_file)
        print("  repr(settings) leaks the key:", "sk-demo-from-secret-file" in repr(settings))
        print("  settings.masked() leaks it:  ", "sk-demo-from-secret-file" in str(settings.masked()))
        ctx.note("pydantic's SecretStr type also hides a value in repr; an explicit masked() view is the simplest thing to teach and test.")
        ctx.note("Log the masked view at start-up so you can see which values were used, without the secret.")

    ctx.step("Where each kind of value belongs")
    rows = [
        ("Baked into the image", "code, dependencies, defaults that are safe to publish"),
        ("environment: / env_file: in compose", "URLs, model name, log level, concurrency"),
        ("Docker secret (file at /run/secrets/NAME)", "API keys, passwords, tokens; read through NAME_FILE"),
        ("Platform secret manager", "the same idea in the cloud: Secret Manager, Key Vault, Kubernetes Secrets"),
    ]
    for place, what in rows:
        print(f"  {place:<44} {what}")
    print("  See docker-compose.yml in this folder for the secrets: section.")
    print("  Why a file and not an env var? Env vars show in `docker inspect`, in crash dumps and are inherited by child processes.")


if __name__ == "__main__":
    main()
