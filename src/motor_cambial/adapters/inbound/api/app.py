"""API REST do Motor de Consolidação Cambial (adapter inbound HTTP).

Segundo adapter inbound (irmão da CLI): expõe o pipeline por HTTP reaproveitando
o composition root e os use cases. Mantém a regra adapters → application → domain.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import TypeAdapter

from motor_cambial.adapters.inbound.api.models import ConsolidarRequest
from motor_cambial.application.use_cases.reprocessar_por_data import (
    reprocessar_por_data,
)
from motor_cambial.composition_root import (
    construir_providers_base,
    construir_repository,
    envolver_com_cache,
)
from motor_cambial.config import Config
from motor_cambial.domain.errors import (
    DomainError,
    PersistenciaIndisponivel,
    RespostaInvalida,
)
from motor_cambial.domain.resultado_consolidacao import RegistroHistorico
from motor_cambial.domain.rules.alertas import ConfiguracaoAlerta

logger = logging.getLogger(__name__)

_HISTORICO_ADAPTER = TypeAdapter(tuple[RegistroHistorico, ...])


def criar_app(config: Config | None = None) -> FastAPI:
    """Factory da app FastAPI (injeta Config para testabilidade)."""
    config = config or Config()
    repositorio = construir_repository(config)
    providers_base = construir_providers_base(config)

    app = FastAPI(title="Motor de Consolidação Cambial", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(PersistenciaIndisponivel)
    def _persistencia(_request, exc: PersistenciaIndisponivel) -> JSONResponse:
        return JSONResponse(status_code=503, content={"erro": str(exc)})

    @app.exception_handler(RespostaInvalida)
    def _resposta_invalida(_request, exc: RespostaInvalida) -> JSONResponse:
        return JSONResponse(status_code=422, content={"erro": str(exc)})

    @app.exception_handler(DomainError)
    def _domain(_request, exc: DomainError) -> JSONResponse:
        # DomainError sem handler específico = bug do motor (ex.: TipoNaoSuportado):
        # loga o traceback para não virar um 500 silencioso (observabilidade).
        logger.error("erro de domínio não tratado no endpoint: %s", exc, exc_info=exc)
        return JSONResponse(status_code=500, content={"erro": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/consolidacoes")
    def consolidar_endpoint(req: ConsolidarRequest) -> Response:
        modo_live = config.modo_live if req.modo_live is None else req.modo_live
        providers = envolver_com_cache(providers_base, config.cache_dir, modo_live)
        overrides: dict[str, Decimal] = {}
        if req.limite_percentual is not None:
            overrides["limite_percentual"] = req.limite_percentual
        if req.limite_absoluto is not None:
            overrides["limite_absoluto_brl"] = req.limite_absoluto
        config_alerta = ConfiguracaoAlerta(**overrides)
        data_ref = req.data_referencia or date.today()
        janela = (
            req.janela_dias
            if req.janela_dias is not None
            else config.janela_fallback_dias
        )
        resultado = reprocessar_por_data(
            req.exposicoes, providers, data_ref, repositorio, config_alerta, janela
        )
        return Response(
            content=resultado.model_dump_json(), media_type="application/json"
        )

    @app.get("/consolidacoes/{data_referencia}/{hash_conjunto}")
    def buscar_endpoint(data_referencia: date, hash_conjunto: str) -> Response:
        resultado = repositorio.buscar(data_referencia, hash_conjunto)
        if resultado is None:
            raise HTTPException(status_code=404, detail="consolidação não encontrada")
        return Response(
            content=resultado.model_dump_json(), media_type="application/json"
        )

    @app.get("/consolidacoes/{data_referencia}/{hash_conjunto}/historico")
    def historico_endpoint(data_referencia: date, hash_conjunto: str) -> Response:
        registros = repositorio.buscar_historico(data_referencia, hash_conjunto)
        return Response(
            content=_HISTORICO_ADAPTER.dump_json(tuple(registros)),
            media_type="application/json",
        )

    return app


app = criar_app()
