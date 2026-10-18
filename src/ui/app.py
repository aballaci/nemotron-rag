"""Streamlit UI for the Nemotron RAG Agent.

Connects to the FastAPI backend at http://localhost:8000 (override with
RAG_API_BASE_URL env var). Two tabs:

- Ask — natural-language question with ABAC-filtered RAG answer + citations.
- Ingest — add a raw document to the knowledge base.
"""

from __future__ import annotations

import os
import random
import re
from typing import Any

import requests
import streamlit as st

API_BASE = os.getenv("RAG_API_BASE_URL", "http://localhost:8000")

# Tier names from spec-kit/policy/classification.md
TIER_LABELS = {1: "Public", 2: "Internal", 3: "Confidential", 4: "Restricted"}
TIER_COLORS = {1: "green", 2: "blue", 3: "orange", 4: "red"}
SNIPPET_MARKUP = re.compile(r"[#*|`>_]+")


def _auth_headers() -> dict[str, str]:
    """Return Authorization header if a JWT token is stored in session state."""
    token = st.session_state.get("jwt_token", "")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _citation_ref(src: dict[str, Any]) -> str:
    return f"{src.get('doc_id', '?')}#{src.get('chunk_index', '?')}"


def _number_citations(answer: str, sources: list[dict[str, Any]]) -> str:
    """Replace raw chunk refs (doc-001#0) in the answer with [n] markers."""
    for i, src in enumerate(sources, 1):
        ref = re.escape(_citation_ref(src))
        answer = re.sub(rf"[\[(]?(?:Chunk\s+)?{ref}[\])]?", f"**[{i}]**", answer)
    return answer


def _plain_snippet(text: str) -> str:
    """Flatten markdown so a snippet can't render as headings or tables."""
    return " ".join(SNIPPET_MARKUP.sub(" ", text).split())


def _render_sources(sources: list[dict[str, Any]]) -> None:
    st.markdown("##### Sources")
    for i, src in enumerate(sources, 1):
        level = src.get("confidentiality_level", 0)
        tier = TIER_LABELS.get(level, f"Level {level}")
        color = TIER_COLORS.get(level, "gray")
        with st.container(border=True):
            st.markdown(
                f"**[{i}] {src.get('title') or src.get('doc_id', '?')}**  \n"
                f":{color}-badge[{tier}] :gray-badge[{src.get('department', '?')}] "
                f"`{_citation_ref(src)}` · relevance {src.get('score', 0):.2f}"
            )
            with st.expander("Excerpt"):
                st.text(_plain_snippet(src.get("text_snippet", "")))


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
            st.success(_number_citations(answer, sources))
        else:
            st.warning(answer)

        st.caption(f"Model: {model}  |  Context used: {context_used}")

        if sources:
            _render_sources(sources)


DEPARTMENTS = ["engineering", "hr", "legal", "it", "product", "executive", "all"]
TENANTS = ["t_acme_corp_001", "t_other_company"]
CONFIDENTIALITY_LEVELS = {1: "public", 2: "internal", 3: "confidential", 4: "restricted"}
CLASSIFICATIONS = [
    "public", "internal", "confidential", "restricted",
    "personnel", "compensation", "investigation", "security_incident", "roadmap", "m_and_a",
]

# Suggested documents used by the "Generate" button.
SAMPLE_DOCS: list[dict[str, Any]] = [
    {
        "slug": "remote-work-policy", "title": "Remote Work Policy", "department": "hr",
        "owner": "hr@example.com", "level": 2, "classification": "internal",
        "text": (
            "# Remote Work Policy\n\nEmployees may work remotely up to three days per week "
            "with manager approval. Core hours are 10:00-15:00 local time. Equipment "
            "stipends of up to 500 EUR are available once per year. Security rules: use the "
            "company VPN and a managed laptop for all access to internal systems."
        ),
    },
    {
        "slug": "platform-roadmap-q4", "title": "Platform Roadmap Q4", "department": "product",
        "owner": "cpo@example.com", "level": 3, "classification": "roadmap",
        "text": (
            "# Platform Roadmap Q4\n\n## Goals\n- Launch the self-service onboarding flow.\n"
            "- Migrate the billing service to the new event pipeline.\n- Reduce p95 API "
            "latency below 250 ms.\n\n## Risks\nThe billing migration depends on the data "
            "platform team delivering the schema registry by mid-quarter."
        ),
    },
    {
        "slug": "incident-postmortem", "title": "Incident Postmortem: Auth Outage", "department": "it",
        "owner": "ciso@example.com", "level": 4, "classification": "security_incident",
        "text": (
            "# Incident Postmortem: Auth Outage\n\nOn the affected date the authentication "
            "service was unavailable for 42 minutes after an expired signing certificate was "
            "not rotated. Impact: all logins failed. Root cause: missing certificate expiry "
            "alert. Actions: add 30-day expiry alerting and an automated rotation job."
        ),
    },
    {
        "slug": "nda-template", "title": "Mutual NDA Template", "department": "legal",
        "owner": "general_counsel@example.com", "level": 3, "classification": "confidential",
        "text": (
            "# Mutual Non-Disclosure Agreement\n\nBoth parties agree to keep Confidential "
            "Information secret for three years from disclosure. Confidential Information "
            "excludes data that is public, independently developed, or already known. "
            "Governing law: the jurisdiction of the disclosing party."
        ),
    },
    {
        "slug": "engineering-onboarding", "title": "Engineering Onboarding Guide", "department": "engineering",
        "owner": "jane.doe@example.com", "level": 1, "classification": "public",
        "text": (
            "# Engineering Onboarding Guide\n\nWelcome! In week one you will set up your "
            "laptop, get repository access, and ship a small change to production with a "
            "buddy. Code review is required for every merge. On-call rotation starts after "
            "your third month."
        ),
    },
    {
        "slug": "company-holidays", "title": "Company Holiday Calendar", "department": "all",
        "owner": "hr@example.com", "level": 1, "classification": "public",
        "text": (
            "# Company Holiday Calendar\n\nThe office is closed on New Year's Day, Good "
            "Friday, Easter Monday, 1 May, 3 October, and from 24 December to 1 January. "
            "Employees receive 28 vacation days per year in addition to public holidays."
        ),
    },
]

_INGEST_DEFAULTS: dict[str, Any] = {
    "ing_doc_id": "",
    "ing_title": "",
    "ing_department": DEPARTMENTS[0],
    "ing_owner": "",
    "ing_level": 1,
    "ing_classification": "internal",
    "ing_tenant_id": TENANTS[0],
    "ing_source_path": "",
    "ing_text": "",
}


def _generate_sample() -> None:
    """Button callback: fill the ingest fields with a suggested document."""
    sample = random.choice(SAMPLE_DOCS)
    suffix = "".join(random.choices("0123456789abcdef", k=4))
    st.session_state.update(
        ing_doc_id=f"{sample['slug']}-{suffix}",
        ing_title=sample["title"],
        ing_department=sample["department"],
        ing_owner=sample["owner"],
        ing_level=sample["level"],
        ing_classification=sample["classification"],
        ing_tenant_id=st.session_state.get("ing_tenant_id", TENANTS[0]),
        ing_source_path=f"/docs/{sample['slug']}.md",
        ing_text=sample["text"],
    )


def render_ingest_tab() -> None:
    st.header("Ingest")
    st.caption("Add a raw document to the knowledge base. It will be chunked, embedded, and indexed.")

    for key, value in _INGEST_DEFAULTS.items():
        st.session_state.setdefault(key, value)

    st.button(
        "✨ Generate",
        on_click=_generate_sample,
        help="Fill all fields with a suggested document. You can edit every value before ingesting.",
    )

    col1, col2 = st.columns(2)
    with col1:
        doc_id = st.text_input("doc_id", key="ing_doc_id", placeholder="unique-doc-id")
        title = st.text_input("title", key="ing_title", placeholder="Document title")
        department = st.selectbox("department", DEPARTMENTS, key="ing_department")
        owner = st.text_input("owner", key="ing_owner", placeholder="jane.doe@example.com")
    with col2:
        confidentiality_level = st.selectbox(
            "confidentiality_level",
            list(CONFIDENTIALITY_LEVELS),
            format_func=lambda lvl: f"{lvl} - {CONFIDENTIALITY_LEVELS[lvl]}",
            key="ing_level",
        )
        classification = st.selectbox("classification", CLASSIFICATIONS, key="ing_classification")
        tenant_id = st.selectbox("tenant_id", TENANTS, key="ing_tenant_id")
        source_path = st.text_input("source_path", key="ing_source_path", placeholder="/docs/policy.md")

    text = st.text_area("text", key="ing_text", height=200, placeholder="Full document text…")

    if st.button("Ingest", type="primary"):
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
