# ADR 0001: Use OpenRouter for All Model Inference

## Status

Accepted

## Context

The RAG agent running on `ace` needs two model capabilities:

1. **Embeddings** — to convert document chunks and user questions into vectors for retrieval.
2. **Chat/completions** — to generate grounded answers from retrieved context.

Options considered:

| Option | Pros | Cons |
|--------|------|------|
| **Local inference on `ace`** (vLLM, Ollama, TGI, sentence-transformers) | No API cost, data never leaves the box | Requires GPU VRAM (Nemotron-3.5-Super-VL needs 24GB+), CUDA driver management, model downloads, slower iteration on model swaps |
| **OpenRouter API** (`nvidia/nemotron-3-embed-1b:free`, `nvidia/nemotron-3.5-super-vl`) | No local GPU needed, instant model swaps, pay-per-token, `ace` stays a lightweight orchestration plane | Requires internet, per-token cost, third-party data processing |
| **NVIDIA NIM direct** | Similar to OpenRouter, NVIDIA-native | Slightly different auth/endpoint model, less model variety |

## Decision

Use **OpenRouter** as the sole inference provider.

- Embeddings: `nvidia/nemotron-3-embed-1b:free` via `POST /embeddings` with `input_type: "passage"` / `"query"`.
- Chat: `nvidia/nemotron-3.5-super-vl` via `POST /chat/completions`.
- `ace` runs no model-serving containers (no vLLM, no Ollama, no local Torch inference).
- All model traffic is outbound HTTPS to `https://openrouter.ai/api/v1`.

## Consequences

### Positive
- `ace` requires no GPU; CPU and RAM are sufficient for orchestration, vector storage, and metadata.
- Model upgrades are configuration changes (`OPENROUTER_CHAT_MODEL`), not infrastructure changes.
- Fast iteration during the learning exercise.

### Negative
- Recurring per-token cost for embeddings and chat.
- Dependency on OpenRouter uptime and API key validity.
- Documents and questions leave `ace` over HTTPS to a third party; acceptable for non-regulated data, requires review for regulated data.

### Mitigations
- Store `OPENROUTER_API_KEY` in Docker secrets or a restricted `.env` (`chmod 600`), never in git.
- Audit log records model used per query (`model`, `latency_ms`, `token_count`).
- If data sovereignty becomes a hard requirement, swap the `OpenRouter*Adapter` implementations for local inference behind the same ports.
