"""00.3/3  Typed configuration for the helpdesk assistant

Environment variables are all strings. A typo in one of them should stop the program at
startup with a clear message, not three hours later with a strange error. This script gives
the course's running example, the Larkspur Labs helpdesk assistant, a configuration object
with types and rules (built with pydantic), filled from a temporary .env. It loads a good
file, then a broken one. It makes no model calls.

Run it:   ./run 00.3/3          (Windows: run 00.3/3)
"""

import tempfile
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field, SecretStr, ValidationError

from labkit import lesson

GOOD_ENV = """HELPDESK_COMPANY=Larkspur Labs
HELPDESK_MAX_REPLY_SENTENCES=4
HELPDESK_ESCALATION_EMAIL=it-escalations@larkspur.example
HELPDESK_OFFICE_HOURS_ONLY=true
HELPDESK_TICKET_SYSTEM_TOKEN=tok-INVENTED-0000-not-a-real-secret
"""

# The same file after a tired edit: a word where a number belongs, a broken email, a missing token.
BROKEN_ENV = """HELPDESK_COMPANY=Larkspur Labs
HELPDESK_MAX_REPLY_SENTENCES=four
HELPDESK_ESCALATION_EMAIL=it-escalations
HELPDESK_OFFICE_HOURS_ONLY=true
"""


class HelpdeskConfig(BaseModel):
    """Everything the helpdesk assistant needs to know before it starts."""

    company: str = Field(min_length=1)
    max_reply_sentences: int = Field(ge=1, le=10)
    escalation_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    office_hours_only: bool = False
    ticket_system_token: SecretStr  # SecretStr prints as ********** wherever it ends up


def load_config(env_file: Path) -> HelpdeskConfig:
    """Read HELPDESK_* lines from a .env file and validate them."""
    values = dotenv_values(env_file)
    prefix = "HELPDESK_"
    fields = {name[len(prefix):].lower(): value for name, value in values.items() if name.startswith(prefix)}
    return HelpdeskConfig(**fields)


@lesson("00.3/3", "Typed configuration for the helpdesk assistant")
def main(ctx):
    with tempfile.TemporaryDirectory() as folder:
        good, broken = Path(folder) / "good.env", Path(folder) / "broken.env"
        good.write_text(GOOD_ENV, encoding="utf-8")
        broken.write_text(BROKEN_ENV, encoding="utf-8")

        ctx.step("Load a correct .env into a typed object")
        config = load_config(good)
        ctx.show_data(
            "HelpdeskConfig",
            {
                "company": config.company,
                "max_reply_sentences": f"{config.max_reply_sentences} ({type(config.max_reply_sentences).__name__})",
                "escalation_email": config.escalation_email,
                "office_hours_only": f"{config.office_hours_only} ({type(config.office_hours_only).__name__})",
                "ticket_system_token": str(config.ticket_system_token),
            },
        )
        ctx.note("'4' became the integer 4 and 'true' became True. The token is a SecretStr: it masks itself when printed.")
        ctx.note("The code that needs the real token asks for it on purpose: config.ticket_system_token.get_secret_value()")

        ctx.step("Load a broken .env")
        ctx.note("Three mistakes: 'four' is not a number, the email has no @, and the token line is missing.")
        try:
            load_config(broken)
            ctx.note("Unexpected: the broken file was accepted.")
        except ValidationError as error:
            ctx.note(f"Rejected at startup with {error.error_count()} problem(s):")
            for problem in error.errors():
                setting = "HELPDESK_" + str(problem["loc"][0]).upper()
                ctx.note(f"  {setting}: {problem['msg']}")

        ctx.step("Why this matters for the assistant")
        ctx.note("Every problem is reported at once, by setting name, before a single ticket is answered.")
        ctx.note("Without validation the assistant would start, then fail in front of an employee.")


if __name__ == "__main__":
    main()
