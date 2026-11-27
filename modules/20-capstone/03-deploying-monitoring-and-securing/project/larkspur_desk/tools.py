"""Two tools: one reads, one writes. Arguments are validated before anything happens.

The ticket store is an in-memory stand-in for the real helpdesk API, so the project runs anywhere.
"""

import json
import threading
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class LookupArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_id: str = Field(pattern=r"^LL-\d{4}$")


class OpenArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["network", "hardware", "software", "access", "other"]
    summary: str = Field(min_length=5, max_length=200)


TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "lookup_ticket",
        "description": "Read the status of an existing ticket by its id, for example LL-1001. Read only.",
        "parameters": LookupArgs.model_json_schema()}},
    {"type": "function", "function": {
        "name": "open_ticket",
        "description": "Open a NEW ticket for the IT desk when the user needs a person to act. Creates a record.",
        "parameters": OpenArgs.model_json_schema()}},
]


class TicketStore:
    def __init__(self):
        self.tickets = {
            "LL-1001": {"status": "open", "category": "access", "summary": "Locked out after five wrong passwords"},
            "LL-1002": {"status": "resolved", "category": "hardware", "summary": "Docking station replaced"},
        }
        self.next_number = 2001
        self._lock = threading.Lock()  # the service handles requests on several threads

    def call(self, name, raw_arguments):
        """Run a tool. Always returns a string the model can read; never raises on bad input."""
        try:
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments)
        except (json.JSONDecodeError, TypeError):
            return "error: arguments are not valid JSON"
        try:
            if name == "lookup_ticket":
                args = LookupArgs(**arguments)
                ticket = self.tickets.get(args.ticket_id)
                return json.dumps({"ticket_id": args.ticket_id, **ticket}) if ticket else f"error: no ticket {args.ticket_id}"
            if name == "open_ticket":
                args = OpenArgs(**arguments)
                with self._lock:
                    ticket_id = f"LL-{self.next_number}"
                    self.next_number += 1
                    self.tickets[ticket_id] = {"status": "open", "category": args.category, "summary": args.summary}
                return json.dumps({"ticket_id": ticket_id, "status": "open"})
        except ValidationError as error:
            return "error: " + "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
        return f"error: unknown tool {name}"
