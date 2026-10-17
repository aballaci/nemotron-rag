"""FastAPI application factory.

Wires adapters, use cases, and routes together.
"""

from __future__ import annotations

from fastapi import FastAPI

from api.routes.ingestion import router as ingestion_router


def create_app() -> FastAPI:
    app = FastAPI(title="Nemotron RAG Agent", version="0.1.0")
    app.include_router(ingestion_router, prefix="/api/v1")
    return app
