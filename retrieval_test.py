"""Mini RAG app using NVIDIA Nemotron 3 Embed 1B via OpenRouter.

Reads a question from the console, retrieves relevant documents from a small
knowledge base, and generates an answer using an OpenRouter chat model.

Key mechanics:
  - `input_type`: `"passage"` for documents at indexing time,
    `"query"` for search inputs at retrieval time.
  - L2-normalized embeddings so a simple dot product == cosine similarity.
  - Retrieved context is injected into the LLM prompt to ground the answer.

Environment:
  OPENROUTER_API_KEY   - your OpenRouter API key (required)
  OPENROUTER_BASE_URL  - override base URL (optional,
                         defaults to https://openrouter.ai/api/v1)
  OPENROUTER_CHAT_MODEL - chat model for answer generation (optional,
                         defaults to nvidia/nemotron-3.5-super-vl)
"""

from __future__ import annotations

import os
from typing import List

import numpy as np
import requests

EMBED_MODEL_ID = "nvidia/nemotron-3-embed-1b:free"
CHAT_MODEL_ID = os.getenv(
    "OPENROUTER_CHAT_MODEL", "nvidia/nemotron-3.5-super-vl"
)
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


DOCUMENTS: List[str] = [
    (
        "Brown notebooks are normally mediocre thoughts containers"
        " they contain ideas that it was better they were never written"
    ),
    (
        "Green balls are most probably the favourite toys of my naighbours kids"
        " they also like salty caramel"
    ),
    (
        "John Grey#s favourite socks are blue cashmere. he likes salty caramel"
    ),
    (
        "There are fiver rooms in the apartment at huffelandztrasse 87. There of them painted in blue"
    ),
]


def _embed(texts: List[str], input_type: str, base_url: str, api_key: str) -> np.ndarray:
    """Get L2-normalized embeddings for a list of texts via OpenRouter."""
    url = f"{base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": EMBED_MODEL_ID,
        "input": texts,
        "input_type": input_type,
        "encoding_format": "float",
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    embeddings = [item["embedding"] for item in data["data"]]
    arr = np.array(embeddings, dtype="float32")
    # L2-normalize defensively so dot product == cosine similarity.
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def _chat(
    messages: List[dict], base_url: str, api_key: str, model: str = CHAT_MODEL_ID
) -> str:
    """Call OpenRouter chat completions and return the assistant reply."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def retrieve(question: str, base_url: str, api_key: str, top_k: int = 2) -> List[str]:
    """Return the top_k most relevant documents for the question."""
    # Encode corpus once with passage input_type.
    doc_embeddings = _embed(DOCUMENTS, "passage", base_url, api_key)

    # Encode question with query input_type.
    query_embedding = _embed([question], "query", base_url, api_key)

    similarities = np.dot(doc_embeddings, query_embedding.T).squeeze()
    best_indices = np.argsort(similarities)[::-1][:top_k]

    return [DOCUMENTS[int(idx)] for idx in best_indices]


def build_prompt(question: str, contexts: List[str]) -> List[dict]:
    """Build the chat messages with retrieved context injected."""
    context_block = "\n".join(f"- {c}" for c in contexts)
    system_prompt = (
        "You are a helpful assistant. Answer the user's question using only "
        "the provided context. If the answer is not in the context, say so. "
        "Do not make up information.\n\n"
        f"Context:\n{context_block}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]


def main() -> None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit(
            "OPENROUTER_API_KEY environment variable is not set. "
            "Export your OpenRouter API key and re-run, e.g.:\n"
            "  export OPENROUTER_API_KEY=sk-or-....\n"
            "  python retrieval_test.py"
        )

    base_url = os.getenv("OPENROUTER_BASE_URL", DEFAULT_BASE_URL)

    # Read question from the console.
    try:
        question = input("Your question: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye!")
        return

    if not question:
        print("No question provided. Exiting.")
        return

    # Retrieve relevant context.
    print("Retrieving context...")
    contexts = retrieve(question, base_url, api_key)

    # Generate answer with the LLM.
    print("Generating answer...")
    messages = build_prompt(question, contexts)
    answer = _chat(messages, base_url, api_key)

    print("\n--- Answer ---")
    print(answer)


if __name__ == "__main__":
    main()
