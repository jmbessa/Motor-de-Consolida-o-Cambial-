"""Testes da montagem dos providers (composition root)."""

from motor_cambial.composition_root import construir_providers
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
