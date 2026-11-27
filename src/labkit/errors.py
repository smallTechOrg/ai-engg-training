"""Turn the failures learners actually hit into a plain explanation and a fix."""

from __future__ import annotations

from dataclasses import dataclass

import openai

from labkit.config import ConfigError, Settings

EXIT_FAILED = 1
EXIT_NOT_CONFIGURED = 2
EXIT_SKIPPED = 3


class ServiceUnavailable(Exception):
    """Raise from a lesson when a service it needs (Redis, LangSmith, n8n...) is not set up."""

    def __init__(self, title: str, fixes: list[str]):
        self.title, self.fixes = title, fixes
        super().__init__(title)


@dataclass
class Explained:
    kind: str  # short machine-friendly label, also used by the doctor
    title: str
    fixes: list[str]
    exit_code: int = EXIT_FAILED


def explain(exc: BaseException, settings: Settings | None = None) -> Explained | None:
    """Return an explanation for a known failure, or None for an unexpected one."""
    url = settings.base_url if settings else "LLM_BASE_URL"
    model = settings.model if settings else "LLM_MODEL"

    if isinstance(exc, ModuleNotFoundError) and exc.name:
        from labkit.catalog import MODULE_TO_EXTRA, install_command

        top = exc.name.split(".")[0]
        extra = MODULE_TO_EXTRA.get(top)
        if extra:
            return Explained(
                "missing_extra",
                f"This lesson needs the optional '{extra}' packages, which are not installed.",
                [f"Install them: {install_command(extra)}", "Then run the lesson again."],
                EXIT_SKIPPED,
            )
    if isinstance(exc, ServiceUnavailable):
        return Explained("missing_service", exc.title, exc.fixes, EXIT_SKIPPED)
    if isinstance(exc, ConfigError):
        return Explained(
            "not_configured",
            "The model endpoint is not configured yet.",
            [
                f"Set {', '.join(exc.missing)} in the .env file at the top of the repo.",
                "No .env file? Copy .env.example to .env first.",
                "Then check it with: ./run doctor   (Windows: run doctor)",
            ],
            EXIT_NOT_CONFIGURED,
        )
    if isinstance(exc, openai.AuthenticationError):
        return Explained(
            "bad_key",
            "The endpoint rejected the API key (401).",
            [
                "Check LLM_API_KEY in .env: no quotes, no spaces, not expired.",
                f"Check the key belongs to the provider at {url}.",
            ],
        )
    if isinstance(exc, openai.PermissionDeniedError):
        return Explained(
            "forbidden",
            "The key is valid but not allowed to use this model (403).",
            [f"Check your account has access to '{model}', or set a different LLM_MODEL."],
        )
    if isinstance(exc, openai.NotFoundError):
        return Explained(
            "not_found",
            "The endpoint answered 'not found' (404).",
            [
                f"Most often the model name is wrong: LLM_MODEL is '{model}'.",
                f"Otherwise the address is wrong: LLM_BASE_URL is '{url}' (most providers need it to end in /v1).",
            ],
        )
    if isinstance(exc, openai.RateLimitError):
        return Explained(
            "rate_limited",
            "The provider is rate-limiting you or the account is out of credit (429).",
            ["Wait a minute and run it again.", "If it persists, check the account's quota or billing."],
        )
    if isinstance(exc, openai.APITimeoutError):
        return Explained(
            "timeout",
            "The model took too long to answer.",
            ["Run it again.", "Local models can be slow to load: raise LLM_TIMEOUT in .env (seconds)."],
        )
    if isinstance(exc, openai.APIConnectionError):
        return Explained(
            "unreachable",
            f"Could not connect to {url}.",
            [
                "Check your network, VPN or proxy.",
                "Using a local model? Make sure its server (Ollama, LM Studio) is running.",
                "Check LLM_BASE_URL in .env for typos.",
            ],
        )
    if isinstance(exc, openai.BadRequestError):
        return Explained(
            "bad_request",
            "The endpoint did not accept the request (400).",
            [
                f"The model '{model}' or this provider may not support a feature this lesson uses.",
                f"Provider said: {_short(exc)}",
                "Run ./run doctor to see which capabilities your model has.",
            ],
        )
    if isinstance(exc, openai.APIStatusError):
        return Explained(
            "server_error",
            f"The provider returned an error ({exc.status_code}).",
            [f"Provider said: {_short(exc)}", "This is usually temporary: run it again."],
        )
    return None


def _short(exc: BaseException) -> str:
    return " ".join(str(exc).split())[:300]
