"""Composition root: monta os adapters concretos a partir da Config (DI manual)."""

from __future__ import annotations

import httpx
from sqlalchemy import create_engine

from motor_cambial.adapters.outbound.cache.cache_provider import CacheCotacaoProvider
from motor_cambial.adapters.outbound.frankfurter.client import FrankfurterProvider
from motor_cambial.adapters.outbound.persistence.repository import (
    RepositorioResultadoSQL,
)
from motor_cambial.adapters.outbound.ptax.client import PtaxProvider
from motor_cambial.config import Config
from motor_cambial.domain.enums import Fonte
from motor_cambial.ports.cotacao_provider import CotacaoProvider
from motor_cambial.ports.resultado_repository import ResultadoRepository


def construir_providers(config: Config) -> dict[Fonte, CotacaoProvider]:
    """Monta PtaxProvider e FrankfurterProvider, cada um com cache."""
    ptax = PtaxProvider(
        client=httpx.Client(timeout=config.http_timeout_s, follow_redirects=True),
        base_url=config.ptax_base_url,
        max_retries=config.http_max_retries,
    )
    frankfurter = FrankfurterProvider(
        client=httpx.Client(timeout=config.http_timeout_s, follow_redirects=True),
        base_url=config.frankfurter_base_url,
        max_retries=config.http_max_retries,
    )
    return {
        Fonte.PTAX: CacheCotacaoProvider(ptax, config.cache_dir, config.modo_live),
        Fonte.FRANKFURTER: CacheCotacaoProvider(
            frankfurter, config.cache_dir, config.modo_live
        ),
    }


def construir_repository(config: Config) -> ResultadoRepository:
    """Monta o RepositorioResultadoSQL a partir da URL de conexão da Config."""
    engine = create_engine(config.db_url())
    return RepositorioResultadoSQL(engine)
