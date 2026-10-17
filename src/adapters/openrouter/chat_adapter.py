"""OpenRouter chat adapter.

Calls OpenRouter /chat/completions with nvidia/nemotron-3.5-super-vl.
"""

from __future__ import annotations

import requests

from ports.chat_model_port import ChatModelPort

CHAT_MODEL_ID = "nvidia/nemotron-3.5-super-vl"


class OpenRouterChatAdapter(ChatModelPort):
    """OpenRouter implementation of ChatModelPort."""

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def generate_answer(
        self,
        system_prompt: str,
        user_question: str,
        temperature: float = 0.2,
    ) -> str:
        """Generate an answer using system context + user question."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": CHAT_MODEL_ID,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question},
            ],
            "temperature": temperature,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
