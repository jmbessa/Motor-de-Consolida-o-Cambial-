"""Testes do decorator de cache de cotações."""

from datetime import date
from decimal import Decimal

from motor_cambial.adapters.outbound.cache.cache_provider import CacheCotacaoProvider
from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.models import CotacaoNormalizada


class _ProviderContador:
    """Provider fake que conta chamadas e devolve uma cotação fixa."""

    fonte = Fonte.FRANKFURTER

    def __init__(self):
        self.chamadas = 0

    def buscar_cotacoes(self, moeda, data_inicial, data_final):
        self.chamadas += 1
        return [
            CotacaoNormalizada.de_frankfurter(
                moeda=moeda, data_referencia=data_inicial, taxa="5.0599"
            )
        ]


def test_hit_em_memoria_nao_rebusca(tmp_path):
    inner = _ProviderContador()
    cache = CacheCotacaoProvider(inner, cache_dir=tmp_path)
    args = (Moeda.USD, date(2026, 6, 1), date(2026, 6, 8))

    primeira = cache.buscar_cotacoes(*args)
    segunda = cache.buscar_cotacoes(*args)

    assert inner.chamadas == 1  # segunda veio do cache
    assert primeira[0].taxa_compra == Decimal("5.0599")
    assert segunda[0].taxa_compra == Decimal("5.0599")


def test_persiste_e_recarrega_de_arquivo(tmp_path):
    inner1 = _ProviderContador()
    CacheCotacaoProvider(inner1, cache_dir=tmp_path).buscar_cotacoes(
        Moeda.USD, date(2026, 6, 1), date(2026, 6, 8)
    )
    # Nova instância (memória vazia) deve carregar do arquivo, sem chamar o inner.
    inner2 = _ProviderContador()
    cotacoes = CacheCotacaoProvider(inner2, cache_dir=tmp_path).buscar_cotacoes(
        Moeda.USD, date(2026, 6, 1), date(2026, 6, 8)
    )
    assert inner2.chamadas == 0
    assert cotacoes[0].taxa_compra == Decimal("5.0599")


def test_modo_live_ignora_cache_e_rebusca(tmp_path):
    inner = _ProviderContador()
    cache = CacheCotacaoProvider(inner, cache_dir=tmp_path, modo_live=True)
    args = (Moeda.USD, date(2026, 6, 1), date(2026, 6, 8))
    cache.buscar_cotacoes(*args)
    cache.buscar_cotacoes(*args)
    assert inner.chamadas == 2  # sempre busca fresco
