#!/usr/bin/env python3
"""Ingest all synthetic documents into Qdrant using the IngestDocumentUseCase.

Reads data/raw-documents/t_acme_corp_001/index.json and calls the use case
for each document, attaching ABAC metadata and generating OpenRouter embeddings.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adapters.qdrant.qdrant_adapter import QdrantAdapter
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from application.use_cases.ingest_document import IngestDocumentUseCase


def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    # Initialize adapters
    vector_store = QdrantAdapter(host="localhost", port=6333)
    vector_store.create_collection()
    embedding_adapter = OpenRouterEmbeddingAdapter(api_key=api_key)

    use_case = IngestDocumentUseCase(
        embedding_adapter=embedding_adapter,
        vector_store=vector_store,
        document_store=None,  # Not using MinIO for now
    )

    # Read index
    index_path = Path("data/raw-documents/t_acme_corp_001/index.json")
    if not index_path.exists():
        print(f"ERROR: {index_path} not found. Run scripts/generate_test_data.py first.")
        sys.exit(1)

    documents = json.loads(index_path.read_text())
    print(f"Found {len(documents)} documents to ingest\n")

    total_chunks = 0
    total_vectors = 0

    for doc in documents:
        md_path = Path(doc["source_path"])
        if not md_path.exists():
            print(f"Skipping {doc['doc_id']}: file not found at {md_path}")
            continue

        text = md_path.read_text()
        print(f"Ingesting {doc['doc_id']} ({doc['title']})...")
        print(f"  Tier: {doc['confidentiality_level']} | Dept: {doc['department']}")

        result = use_case.execute(
            doc_id=doc["doc_id"],
            title=doc["title"],
            text=text,
            confidentiality_level=doc["confidentiality_level"],
            department=doc["department"],
            classification=doc["classification"],
            owner=doc["owner"],
            tenant_id=doc["tenant_id"],
            source_path=str(md_path),
            chunk_size=512,
            overlap=50,
        )

        print(f"  -> {result.chunks_indexed} chunks, status: {result.status}\n")
        total_chunks += result.chunks_indexed
        total_vectors += result.vectors_written

    print(f"Ingestion complete!")
    print(f"Total documents: {len(documents)}")
    print(f"Total chunks: {total_chunks}")
    print(f"Total vectors in Qdrant: {total_vectors}")


if __name__ == "__main__":
    main()
