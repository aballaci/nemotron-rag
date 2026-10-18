"""Streamlit UI for the Nemotron RAG Agent.

Connects to the FastAPI backend at http://localhost:8000 (override with
RAG_API_BASE_URL env var). Two tabs:

- Ask — natural-language question with ABAC-filtered RAG answer + citations.
- Ingest — add a raw document to the knowledge base.
"""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

API_BASE = os.getenv("RAG_API_BASE_URL", "http://localhost:8000")


def _auth_headers() -> dict[str, str]:
    """Return Authorization header if a JWT token is stored in session state."""
    token = st.session_state.get("jwt_token", "")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        resp = requests.post(
            f"{API_BASE}{path}",
            json=payload,
            headers=_auth_headers(),
            timeout=120,
        )
        if resp.status_code == 401:
            st.error(
                "Authentication failed: invalid or missing JWT. "
                "Enter a valid token in the sidebar."
            )
            return {}
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:  # noqa: BLE001
        st.error(f"Backend error ({API_BASE}{path}): {exc}")
        return {}


def render_ask_tab() -> None:
    st.header("Ask")
    st.caption("Ask a question against your private knowledge base. Answers are grounded in retrieved chunks only.")

    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input("Question", placeholder="e.g. What is the Q4 travel policy?")
    with col2:
        top_k = st.number_input("Top K", min_value=1, max_value=20, value=5, step=1)

    if st.button("Ask", type="primary", disabled=not question):
        with st.spinner("Retrieving and generating…"):
            data = _post("/api/v1/ask", {"question": question, "top_k": int(top_k)})

        if not data:
            return

        answer = data.get("answer", "")
        sources = data.get("sources", []) or []
        model = data.get("model", "unknown")
        context_used = data.get("context_used", False)

        if context_used:
            st.success(answer)
        else:
            st.warning(answer)

        st.caption(f"Model: {model}  |  Context used: {context_used}")

        if sources:
            st.subheader("Sources")
            for i, src in enumerate(sources, 1):
                with st.expander(
                    f"[{i}] {src.get('doc_id', '?')} · chunk {src.get('chunk_index', '?')} "
                    f"· score {src.get('score', 0):.3f}"
                ):
                    st.write(src.get("text_snippet", ""))
                    st.caption(
                        f"department={src.get('department', '?')} · "
                        f"confidentiality_level={src.get('confidentiality_level', '?')}"
                    )


def render_ingest_tab() -> None:
    st.header("Ingest")
    st.caption("Add a raw document to the knowledge base. It will be chunked, embedded, and indexed.")

    with st.form("ingest_form"):
        col1, col2 = st.columns(2)
        with col1:
            doc_id = st.text_input("doc_id", placeholder="unique-doc-id")
            title = st.text_input("title", placeholder="Document title")
            department = st.text_input("department", placeholder="engineering")
            owner = st.text_input("owner", placeholder="jane.doe@example.com")
        with col2:
            confidentiality_level = st.number_input(
                "confidentiality_level (1-4)", min_value=1, max_value=4, value=1, step=1
            )
            classification = st.text_input("classification", placeholder="internal")
            tenant_id = st.text_input("tenant_id", placeholder="t_acme_corp_001")
            source_path = st.text_input("source_path", placeholder="/docs/policy.md")

        text = st.text_area("text", height=200, placeholder="Full document text…")
        submitted = st.form_submit_button("Ingest", type="primary")

    if submitted:
        if not all([doc_id, title, text, department, owner, tenant_id]):
            st.error("Please fill in all required fields.")
            return
        with st.spinner("Ingesting…"):
            data = _post(
                "/api/v1/ingest",
                {
                    "doc_id": doc_id,
                    "title": title,
                    "text": text,
                    "confidentiality_level": int(confidentiality_level),
                    "department": department,
                    "classification": classification,
                    "owner": owner,
                    "tenant_id": tenant_id,
                    "source_path": source_path,
                },
            )
        if data:
            st.success(
                f"Ingested `{doc_id}`: {data.get('chunks_indexed')} chunks, "
                f"{data.get('vectors_written')} vectors ({data.get('status')})"
            )


def main() -> None:
    st.set_page_config(page_title="Nemotron RAG", page_icon="🔍", layout="wide")
    st.title("🔍 Nemotron RAG Agent")
    st.caption("Private knowledge base with ABAC-filtered retrieval via OpenRouter / Nemotron.")

    with st.sidebar:
        st.header("Authentication")
        token = st.text_input(
            "JWT Bearer Token",
            type="password",
            value=st.session_state.get("jwt_token", ""),
            help="Generate a dev token via the JWT adapter. See README Authentication section.",
        )
        if token:
            st.session_state.jwt_token = token
            st.success("Token set")
        else:
            st.session_state.pop("jwt_token", None)
            st.warning("No token — API calls will return 401")

    tab_ask, tab_ingest = st.tabs(["Ask", "Ingest"])
    with tab_ask:
        render_ask_tab()
    with tab_ingest:
        render_ingest_tab()


if __name__ == "__main__":
    main()
