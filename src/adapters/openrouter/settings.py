"""Resolve the OpenRouter API key from env or a mounted secret file."""

from __future__ import annotations

import os


def load_openrouter_api_key() -> str:
    path = os.getenv("OPENROUTER_API_KEY_FILE")
    if path:
        with open(path) as f:
            return f.read().strip()
    return os.getenv("OPENROUTER_API_KEY", "")
