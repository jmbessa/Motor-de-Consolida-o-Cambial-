"""Testes dos GET de consulta (por data+hash e histórico)."""

from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from motor_cambial.adapters.inbound.api.app import criar_app
from motor_cambial.domain.resultado_consolidacao import (
    RegistroHistorico,
    ResultadoConsolidacao,
)
from motor_cambial.domain.services.consolidador import consolidar

_HASH = "a" * 64


def _resultado():
    return ResultadoConsolidacao(
        data_referencia=date(2026, 6, 5), hash_conjunto=_HASH,
        posicoes=(), visao=consolidar([]))


def _client(monkeypatch, repo):
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
        lambda base, cache_dir, modo_live: {},
    )
    return TestClient(criar_app())


class _RepoBase:
    def salvar(self, resultado): ...
    def buscar(self, data_referencia, hash_conjunto): return None
    def buscar_historico(self, data_referencia, hash_conjunto): return ()


def test_get_encontrado_retorna_200(monkeypatch):
    class _Repo(_RepoBase):
        def buscar(self, data_referencia, hash_conjunto):
            return _resultado()
    client = _client(monkeypatch, _Repo())
    r = client.get(f"/consolidacoes/2026-06-05/{_HASH}")
    assert r.status_code == 200
    assert r.json()["hash_conjunto"] == _HASH


def test_get_nao_encontrado_retorna_404(monkeypatch):
    client = _client(monkeypatch, _RepoBase())  # buscar -> None
    r = client.get(f"/consolidacoes/2026-06-05/{_HASH}")
    assert r.status_code == 404


def test_get_historico_retorna_trilha(monkeypatch):
    reg = RegistroHistorico(
        resultado=_resultado(),
        processado_em=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
        num_processamento=1,
    )

    class _Repo(_RepoBase):
        def buscar_historico(self, data_referencia, hash_conjunto):
            return (reg,)

    client = _client(monkeypatch, _Repo())
    r = client.get(f"/consolidacoes/2026-06-05/{_HASH}/historico")
    assert r.status_code == 200
    corpo = r.json()
    assert len(corpo) == 1
    assert corpo[0]["num_processamento"] == 1
