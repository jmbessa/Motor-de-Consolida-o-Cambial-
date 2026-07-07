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


def test_arquivo_corrompido_e_tratado_como_cache_vazio(tmp_path):
    inner = _ProviderContador()
    (tmp_path / f"{inner.fonte.value}.json").write_text("isto não é json", encoding="utf-8")
    cache = CacheCotacaoProvider(inner, cache_dir=tmp_path)  # não deve crashar ao carregar
    cotacoes = cache.buscar_cotacoes(Moeda.USD, date(2026, 6, 1), date(2026, 6, 8))
    assert inner.chamadas == 1  # tratou corrompido como vazio e buscou
    assert cotacoes[0].taxa_compra == Decimal("5.0599")


def test_registro_de_cache_malformado_e_tratado_como_miss(tmp_path):
    import json
    inner = _ProviderContador()
    # grava um registro malformado sob a chave que será consultada
    chave = f"{Moeda.USD.value}|2026-06-01|2026-06-08"
    (tmp_path / f"{inner.fonte.value}.json").write_text(
        json.dumps({chave: [{"lixo": "sem campos válidos"}]}), encoding="utf-8"
    )
    cache = CacheCotacaoProvider(inner, cache_dir=tmp_path)
    cotacoes = cache.buscar_cotacoes(Moeda.USD, date(2026, 6, 1), date(2026, 6, 8))
    assert inner.chamadas == 1  # registro ruim tratado como miss -> rebuscou
    assert cotacoes[0].taxa_compra == Decimal("5.0599")


def test_falha_ao_salvar_nao_descarta_resultado(tmp_path, monkeypatch):
    inner = _ProviderContador()
    cache = CacheCotacaoProvider(inner, cache_dir=tmp_path)
    monkeypatch.setattr(cache, "_salvar", lambda: (_ for _ in ()).throw(OSError("disco cheio")))
    cotacoes = cache.buscar_cotacoes(Moeda.USD, date(2026, 6, 1), date(2026, 6, 8))
    assert cotacoes[0].taxa_compra == Decimal("5.0599")  # resultado preservado apesar do erro de escrita


def test_round_trip_preserva_timestamp_tz_aware(tmp_path):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from motor_cambial.domain.enums import Fonte
    from motor_cambial.domain.models import CotacaoNormalizada

    ts = datetime(2026, 6, 5, 13, 3, 38, tzinfo=ZoneInfo("America/Sao_Paulo"))

    class _PtaxFake:
        fonte = Fonte.PTAX
        def __init__(self):
            self.chamadas = 0
        def buscar_cotacoes(self, moeda, data_inicial, data_final):
            self.chamadas += 1
            return [CotacaoNormalizada.de_ptax(
                moeda=moeda, data_referencia=data_inicial,
                taxa_compra="5.12", taxa_venda="5.13", timestamp=ts)]

    CacheCotacaoProvider(_PtaxFake(), cache_dir=tmp_path).buscar_cotacoes(
        Moeda.USD, date(2026, 6, 5), date(2026, 6, 5))
    inner2 = _PtaxFake()
    cot = CacheCotacaoProvider(inner2, cache_dir=tmp_path).buscar_cotacoes(
        Moeda.USD, date(2026, 6, 5), date(2026, 6, 5))[0]
    assert inner2.chamadas == 0  # veio do arquivo
    assert cot.timestamp == ts  # mesmo instante
    assert cot.timestamp.utcoffset().total_seconds() == -3 * 3600
