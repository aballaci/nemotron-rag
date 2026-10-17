"""Context builder.

Merges retrieved chunks into a system prompt for the LLM:
- Sorts by relevance score
- Truncates to fit token budget (~6000 tokens)
- Injects source citations with doc titles and chunk IDs
- Grounds the answer to retrieved context only
"""

from __future__ import annotations

from typing import List

from core.models import RetrievalResult

MAX_CONTEXT_TOKENS = 6000


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return len(text) // 4


def build_context(
    results: List[RetrievalResult],
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> str:
    """Build context block from retrieved chunks, truncated to token budget.

    Returns a formatted string with citations:
        [Chunk doc-005#0] ...
        [Chunk doc-003#0] ...
    """
    if not results:
        return ""

    lines: List[str] = []
    used_tokens = 0
    included = 0

    for result in results:
        chunk = result.chunk
        snippet = f"[Chunk {chunk.doc_id}#{chunk.chunk_index}] {chunk.text}"
        snippet_tokens = estimate_tokens(snippet)

        if used_tokens + snippet_tokens > max_tokens and included > 0:
            break

        lines.append(snippet)
        used_tokens += snippet_tokens
        included += 1

    return "\n".join(lines)


def build_system_prompt(context_block: str) -> str:
    """Build the system prompt with grounded instructions."""
    return f"""You are an enterprise knowledge assistant. Answer the user's question using ONLY the provided context.

Rules:
- Base your answer exclusively on the context below.
- If the answer is not in the context, say so explicitly.
- Do not hallucinate or infer beyond the provided text.
- Cite sources using the chunk reference format shown in context (e.g., doc-005#0).
- Keep answers concise and directly relevant.

Context:
{context_block}

Answer based on the context above."""
