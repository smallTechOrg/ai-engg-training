"""labkit: shared plumbing for the lessons.

It supplies the configured client, readable output, token totals, run logs and friendly
errors. It deliberately does NOT wrap the model calls being taught: lessons call the SDK
directly so that what you read is the real API.
"""

from labkit.config import ConfigError, Settings, load_settings, repo_root
from labkit.client import get_client
from labkit.lesson import Lesson, lesson

__all__ = [
    "ConfigError",
    "Lesson",
    "Settings",
    "get_client",
    "lesson",
    "load_settings",
    "repo_root",
]
