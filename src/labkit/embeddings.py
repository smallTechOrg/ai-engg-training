"""Embeddings for the lessons that need them (module 03 onwards).

Two backends, chosen by settings:

- **Your endpoint**: when EMBEDDING_MODEL names a hosted model, texts go to
  `client.embeddings.create(...)` on EMBEDDING_BASE_URL (default: LLM_BASE_URL).
- **On this machine**: when EMBEDDING_MODEL is empty or starts with `local:`, the
  `fastembed` package runs a small open model on the CPU. Many OpenAI-compatible providers
  offer no embeddings, so this keeps the RAG lessons working everywhere. The model
  (about 70 MB) downloads on first use and is cached.
"""

from __future__ import annotations

import os
from functools import lru_cache

from labkit.config import Settings, load_settings

DEFAULT_LOCAL_MODEL = "BAAI/bge-small-en-v1.5"


def backend(settings: Settings | None = None) -> tuple[str, str]:
    """('endpoint' | 'local', model name)."""
    settings = settings or load_settings()
    name = settings.embedding_model
    if not name or name.startswith("local:"):
        return "local", (name[len("local:"):] if name else "") or DEFAULT_LOCAL_MODEL
    return "endpoint", name


@lru_cache(maxsize=2)
def _local_model(name: str):
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")  # keep lesson output readable
    os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    import logging
    import warnings

    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", module="huggingface_hub")
    from fastembed import TextEmbedding  # optional 'rag' extra

    return TextEmbedding(model_name=name)


def embed(texts: list[str], settings: Settings | None = None, on_wire=None) -> tuple[list[list[float]], int | None, str]:
    """Return (vectors, prompt tokens if reported, backend description)."""
    settings = settings or load_settings()
    kind, name = backend(settings)
    if kind == "local":
        vectors = [list(map(float, v)) for v in _local_model(name).embed(list(texts))]
        return vectors, None, f"local:{name}"
    from labkit.client import get_client

    client = get_client(settings, embeddings=True, on_wire=on_wire)
    result = client.embeddings.create(model=name, input=list(texts))
    usage = getattr(getattr(result, "usage", None), "prompt_tokens", None)
    return [item.embedding for item in sorted(result.data, key=lambda d: d.index)], usage, f"endpoint:{name}"
