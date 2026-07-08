"""Testes do POST /consolidacoes (TestClient, sem rede/DB, dependências fake)."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from motor_cambial.adapters.inbound.api.app import criar_app
from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.errors import PersistenciaIndisponivel
from motor_cambial.domain.models import CotacaoNormalizada
from motor_cambial.domain.resultado_consolidacao import ResultadoConsolidacao
from motor_cambial.domain.services.consolidador import consolidar


class _ProviderFake:
    def __init__(self, fonte, cotacoes):
        self.fonte = fonte
        self._cotacoes = cotacoes

    def buscar_cotacoes(self, moeda, data_inicial, data_final):
        return self._cotacoes


class _RepoFake:
    def __init__(self):
        self.salvos = []

    def salvar(self, resultado):
        self.salvos.append(resultado)

    def buscar(self, data_referencia, hash_conjunto):
        return None

    def buscar_historico(self, data_referencia, hash_conjunto):
        return ()


def _providers_ok(data_ref):
    return {
        Fonte.PTAX: _ProviderFake(
            Fonte.PTAX,
            [CotacaoNormalizada.de_ptax(
                moeda=Moeda.USD, data_referencia=data_ref,
                taxa_compra="5.00", taxa_venda="5.10")],
        ),
        Fonte.FRANKFURTER: _ProviderFake(
            Fonte.FRANKFURTER,
            [CotacaoNormalizada.de_frankfurter(
                moeda=Moeda.USD, data_referencia=data_ref, taxa="5.05")],
        ),
    }


_BODY = {
    "exposicoes": [
        {"id": "1", "tipo": "payable", "moeda": "USD", "valor": "1000",
         "vencimento": "2026-06-05"}
    ],
    "data_referencia": "2026-06-05",
}


def _client(monkeypatch, repo=None, providers=None):
    repo = repo or _RepoFake()
    provs = providers if providers is not None else _providers_ok(date(2026, 6, 5))
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.construir_repository",
        lambda config: repo,
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.construir_providers_base",
        lambda config: {},
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.envolver_com_cache",
        lambda base, cache_dir, modo_live: provs,
    )
    return TestClient(criar_app()), repo


def test_post_consolida_persiste_e_retorna_resultado(monkeypatch):
    client, repo = _client(monkeypatch)
    r = client.post("/consolidacoes", json=_BODY)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["data_referencia"] == "2026-06-05"
    assert "hash_conjunto" in corpo
    assert len(repo.salvos) == 1


def test_post_serializa_decimal_como_string_nao_float(monkeypatch):
    client, _ = _client(monkeypatch)
    r = client.post("/consolidacoes", json=_BODY)
    assert r.status_code == 200, r.text
    valor_brl = r.json()["posicoes"][0]["conversao_ptax"]["valor_brl"]
    assert isinstance(valor_brl, str)  # lossless: string, nunca float


def test_post_corpo_invalido_vira_422(monkeypatch):
    client, _ = _client(monkeypatch)
    corpo = {"exposicoes": [{"id": "1", "tipo": "payable", "moeda": "USD",
                             "valor": 1000.5, "vencimento": "2026-06-05"}]}
    r = client.post("/consolidacoes", json=corpo)
    assert r.status_code == 422


def test_post_lista_vazia_vira_422(monkeypatch):
    client, _ = _client(monkeypatch)
    r = client.post("/consolidacoes", json={"exposicoes": []})
    assert r.status_code == 422


def test_post_repassa_overrides(monkeypatch):
    capturado = {}

    def _fake_reprocessar(exposicoes, providers, data_referencia, repository,
                          config_alerta, janela):
        capturado["config_alerta"] = config_alerta
        capturado["janela"] = janela
        capturado["data"] = data_referencia
        return ResultadoConsolidacao(
            data_referencia=data_referencia, hash_conjunto="a" * 64,
            posicoes=(), visao=consolidar([]))

    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.reprocessar_por_data",
        _fake_reprocessar,
    )
    client, _ = _client(monkeypatch)
    r = client.post("/consolidacoes",
                    json={**_BODY, "limite_percentual": "3.0", "janela_dias": 10})
    assert r.status_code == 200, r.text
    assert capturado["config_alerta"].limite_percentual == Decimal("3.0")
    assert capturado["janela"] == 10
    assert capturado["data"] == date(2026, 6, 5)


def test_post_persistencia_indisponivel_vira_503(monkeypatch):
    class _RepoQuebrado(_RepoFake):
        def salvar(self, resultado):
            raise PersistenciaIndisponivel("db fora do ar")

    client, _ = _client(monkeypatch, repo=_RepoQuebrado())
    r = client.post("/consolidacoes", json=_BODY)
    assert r.status_code == 503


def test_post_modo_live_no_corpo_chega_ao_envelope(monkeypatch):
    capturado = {}

    def _fake_envolver(base, cache_dir, modo_live):
        capturado["modo_live"] = modo_live
        return _providers_ok(date(2026, 6, 5))

    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.construir_repository",
        lambda config: _RepoFake(),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.construir_providers_base",
        lambda config: {},
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.envolver_com_cache", _fake_envolver
    )
    client = TestClient(criar_app())
    r = client.post("/consolidacoes", json={**_BODY, "modo_live": True})
    assert r.status_code == 200, r.text
    assert capturado["modo_live"] is True


def test_providers_base_construido_uma_vez_e_nao_por_requisicao(monkeypatch):
    chamadas = {"base": 0, "envolver": 0}

    def _fake_base(config):
        chamadas["base"] += 1
        return {}

    def _fake_envolver(base, cache_dir, modo_live):
        chamadas["envolver"] += 1
        return _providers_ok(date(2026, 6, 5))

    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.construir_repository",
        lambda config: _RepoFake(),
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.construir_providers_base", _fake_base
    )
    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.envolver_com_cache", _fake_envolver
    )
    client = TestClient(criar_app())
    assert chamadas["base"] == 1  # base montado no criar_app
    client.post("/consolidacoes", json=_BODY)
    client.post("/consolidacoes", json=_BODY)
    assert chamadas["base"] == 1  # NÃO reconstruído por requisição (fix I-1)
    assert chamadas["envolver"] == 2  # envelope barato, por requisição


def test_post_erro_inesperado_do_motor_vira_500(monkeypatch):
    # DomainError sem handler específico (bug do motor) cai no handler base -> 500.
    from motor_cambial.domain.errors import TipoNaoSuportado

    def _fake_reprocessar(*args, **kwargs):
        raise TipoNaoSuportado("tipo não tratado")

    monkeypatch.setattr(
        "motor_cambial.adapters.inbound.api.app.reprocessar_por_data",
        _fake_reprocessar,
    )
    client, _ = _client(monkeypatch)
    r = client.post("/consolidacoes", json=_BODY)
    assert r.status_code == 500


def test_post_janela_dias_absurda_vira_422(monkeypatch):
    # janela_dias com teto (le=3650) evita OverflowError -> 500 com input patológico.
    client, _ = _client(monkeypatch)
    r = client.post("/consolidacoes", json={**_BODY, "janela_dias": 999999})
    assert r.status_code == 422
