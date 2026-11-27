"""A budget guard: refuse to call the model once a token or call cap is reached.

Caps are per process and reset on restart, which is fine for a safety net; the provider's own spend
limit is the real backstop. Thread-safe, because the service handles requests on several threads.
"""

import threading


class BudgetExceeded(Exception):
    pass


class BudgetGuard:
    def __init__(self, max_tokens, max_calls):
        self.max_tokens, self.max_calls = max_tokens, max_calls
        self.tokens, self.calls = 0, 0
        self._lock = threading.Lock()

    def reserve(self):
        """Count a call BEFORE making it, so concurrent requests cannot all slip under the cap."""
        with self._lock:
            if self.calls >= self.max_calls:
                raise BudgetExceeded(f"call cap reached ({self.max_calls})")
            if self.tokens >= self.max_tokens:
                raise BudgetExceeded(f"token cap reached ({self.max_tokens})")
            self.calls += 1

    def record(self, usage):
        total = getattr(usage, "total_tokens", None)
        if total is None and usage is not None:
            total = (getattr(usage, "prompt_tokens", 0) or 0) + (getattr(usage, "completion_tokens", 0) or 0)
        with self._lock:
            self.tokens += total or 0

    def snapshot(self):
        with self._lock:
            return {"tokens": self.tokens, "max_tokens": self.max_tokens, "calls": self.calls, "max_calls": self.max_calls}


def guarded(chat, guard):
    """Wrap a chat function so every model call passes through the guard."""

    def wrapper(messages, tools):
        guard.reserve()
        response = chat(messages, tools)
        guard.record(getattr(response, "usage", None))
        return response

    return wrapper
