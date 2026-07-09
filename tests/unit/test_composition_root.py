"""Testes do composition_root: providers/repository e split base vs. cache."""

from motor_cambial.adapters.outbound.cache.cache_provider import CacheCotacaoProvider
from motor_cambial.adapters.outbound.frankfurter.client import FrankfurterProvider
from motor_cambial.adapters.outbound.ptax.client import PtaxProvider
from motor_cambial.composition_root import (
    construir_providers,
    construir_providers_base,
    construir_repository,
    envolver_com_cache,
)
from motor_cambial.config import Config
from motor_cambial.domain.enums import Fonte
from motor_cambial.ports.cotacao_provider import CotacaoProvider


def test_monta_os_dois_providers(tmp_path):
    config = Config(cache_dir=tmp_path)
    providers = construir_providers(config)
    assert set(providers) == {Fonte.PTAX, Fonte.FRANKFURTER}
    for fonte, provider in providers.items():
        assert isinstance(provider, CotacaoProvider)
        assert provider.fonte is fonte


def test_monta_o_repository(tmp_path):
    config = Config(db_host="localhost", db_port=3306, db_name="x")
    from motor_cambial.ports.resultado_repository import ResultadoRepository

    repository = construir_repository(config)
    assert isinstance(repository, ResultadoRepository)


def test_construir_providers_base_sem_cache():
    base = construir_providers_base(Config())
    assert set(base) == {Fonte.PTAX, Fonte.FRANKFURTER}
    assert isinstance(base[Fonte.PTAX], PtaxProvider)
    assert isinstance(base[Fonte.FRANKFURTER], FrankfurterProvider)


def test_envolver_com_cache_embrulha_cada_provider(tmp_path):
    base = construir_providers_base(Config())
    envolvidos = envolver_com_cache(base, tmp_path, modo_live=True)
    assert set(envolvidos) == {Fonte.PTAX, Fonte.FRANKFURTER}
    assert isinstance(envolvidos[Fonte.PTAX], CacheCotacaoProvider)
    assert envolvidos[Fonte.PTAX].fonte is Fonte.PTAX


def test_construir_providers_compoe_base_com_cache(tmp_path):
    config = Config(cache_dir=tmp_path)
    providers = construir_providers(config)
    assert isinstance(providers[Fonte.PTAX], CacheCotacaoProvider)
    assert isinstance(providers[Fonte.FRANKFURTER], CacheCotacaoProvider)
