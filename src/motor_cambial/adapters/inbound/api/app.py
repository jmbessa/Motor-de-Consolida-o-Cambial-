"""API REST do Motor de Consolidação Cambial (adapter inbound HTTP).

Segundo adapter inbound (irmão da CLI): expõe o pipeline por HTTP reaproveitando
o composition root e os use cases. Mantém a regra adapters → application → domain.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from motor_cambial.config import Config


def criar_app(config: Config | None = None) -> FastAPI:
    """Factory da app FastAPI (injeta Config para testabilidade)."""
    config = config or Config()
    app = FastAPI(title="Motor de Consolidação Cambial", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = criar_app()
