"""Larkspur desk: a compact reference implementation of the capstone.

Four small parts, each in its own file so you can swap one without touching the rest:

  kb.py          load the knowledge base, search it (lexical, or embeddings plus lexical)
  guardrails.py  check what goes in and what comes out
  tools.py       two tools the model may call, with validated arguments
  graph.py       the wiring: guard -> retrieve -> decide -> answer -> check -> finish

Runs offline with no model (extractive answers) and with any OpenAI-compatible model.
"""

from .graph import Desk, Result  # noqa: F401
from .kb import KnowledgeBase  # noqa: F401
from .tools import TicketStore  # noqa: F401
