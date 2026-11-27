"""00.3/2  Showing settings without leaking secrets

Sooner or later you print your configuration to debug something, and the output ends up
in a screenshot, a log file or a chat message. This script shows the habit that makes
that safe: never print a secret, print a mask. It then shows how this course reads your
real settings, with the key masked. No model calls.

Run it:   ./run 00.3/2          (Windows: run 00.3/2)
"""

from labkit import lesson, load_settings
from labkit.config import mask

# Invented values in the shapes real keys take. Built in pieces so that no scanner
# mistakes this teaching file for a leaked credential.
FAKE_KEYS = {
    "a typical provider key": "sk-" + "Xy7" * 15 + "Qd",
    "a short token": "abc" + "123",
    "nothing at all": "",
}


@lesson("00.3/2", "Showing settings without leaking secrets")
def main(ctx):
    ctx.step("Mask before you print")
    ctx.note("A good mask shows enough to recognise WHICH key it is, and never enough to use it.")
    ctx.show_data("mask(value)", {label: mask(value) for label, value in FAKE_KEYS.items()})
    ctx.note("First three characters, last two, and the length: enough to spot a wrong or truncated key.")

    ctx.step("What is secret and what is not")
    ctx.show_data(
        "The three settings this course needs",
        {
            "LLM_BASE_URL": "not secret: the address of the provider",
            "LLM_MODEL": "not secret: the model name",
            "LLM_API_KEY": "SECRET: anyone holding it can spend your money",
        },
    )

    ctx.step("Your real settings, safely")
    ctx.note("load_settings() reads the .env at the top of the repo; variables already set in the terminal win.")
    settings = load_settings()
    ctx.show_data(
        "load_settings()",
        {
            "read from": ".env file" if settings.env_file_exists else "environment variables only (no .env file)",
            "LLM_BASE_URL": settings.base_url or "(not set)",
            "LLM_MODEL": settings.model or "(not set)",
            "LLM_API_KEY": mask(settings.api_key),
            "LLM_TIMEOUT": settings.timeout,
        },
    )

    ctx.step("Is anything missing?")
    missing = settings.missing()
    if missing:
        ctx.note("Not set: " + ", ".join(missing))
        ctx.note("Values copied unchanged from .env.example (such as 'your-key') count as not set.")
        ctx.note("Edit .env, then check with: ./run doctor")
    else:
        ctx.note("All three required settings are present. Whether they WORK is a different question: ./run doctor asks the endpoint.")


if __name__ == "__main__":
    main()
