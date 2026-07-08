"""Testes do loader de exposições (arquivo JSON -> list[Exposicao])."""

from datetime import date
from decimal import Decimal

import pytest

from motor_cambial.adapters.inbound.cli.loader import carregar_exposicoes
from motor_cambial.domain.enums import Moeda, TipoExposicao
from motor_cambial.domain.errors import RespostaInvalida


def test_carrega_lista_valida(tmp_path):
    arquivo = tmp_path / "exposicoes.json"
    arquivo.write_text(
        '[{"id": "1", "tipo": "payable", "moeda": "USD", "valor": "125000", '
        '"vencimento": "2026-06-05", "descricao": "AWS invoice"}]',
        encoding="utf-8",
    )
    exposicoes = carregar_exposicoes(arquivo)
    assert len(exposicoes) == 1
    exp = exposicoes[0]
    assert exp.id == "1"
    assert exp.tipo is TipoExposicao.PAYABLE
    assert exp.moeda is Moeda.USD
    assert exp.valor == Decimal("125000")
    assert exp.vencimento == date(2026, 6, 5)


def test_preserva_ordem_do_arquivo(tmp_path):
    arquivo = tmp_path / "exposicoes.json"
    arquivo.write_text(
        '[{"id": "2", "tipo": "receivable", "moeda": "EUR", "valor": "1", '
        '"vencimento": "2026-06-08"}, '
        '{"id": "1", "tipo": "payable", "moeda": "USD", "valor": "1", '
        '"vencimento": "2026-06-05"}]',
        encoding="utf-8",
    )
    exposicoes = carregar_exposicoes(arquivo)
    assert [e.id for e in exposicoes] == ["2", "1"]


def test_arquivo_ausente_levanta_resposta_invalida(tmp_path):
    with pytest.raises(RespostaInvalida):
        carregar_exposicoes(tmp_path / "nao-existe.json")


def test_json_malformado_levanta_resposta_invalida(tmp_path):
    arquivo = tmp_path / "exposicoes.json"
    arquivo.write_text("{ isso nao e json", encoding="utf-8")
    with pytest.raises(RespostaInvalida):
        carregar_exposicoes(arquivo)


def test_nao_lista_levanta_resposta_invalida(tmp_path):
    arquivo = tmp_path / "exposicoes.json"
    arquivo.write_text('{"id": "1"}', encoding="utf-8")
    with pytest.raises(RespostaInvalida):
        carregar_exposicoes(arquivo)


def test_item_invalido_levanta_resposta_invalida_com_indice(tmp_path):
    arquivo = tmp_path / "exposicoes.json"
    arquivo.write_text(
        '[{"id": "1", "tipo": "payable", "moeda": "USD", "valor": "125000", '
        '"vencimento": "2026-06-05"}, '
        '{"id": "2", "tipo": "invalido", "moeda": "USD", "valor": "1", '
        '"vencimento": "2026-06-05"}]',
        encoding="utf-8",
    )
    with pytest.raises(RespostaInvalida, match="índice 1"):
        carregar_exposicoes(arquivo)


def test_valor_string_preserva_precisao(tmp_path):
    arquivo = tmp_path / "exposicoes.json"
    arquivo.write_text(
        '[{"id": "1", "tipo": "payable", "moeda": "USD", "valor": "98000.50", '
        '"vencimento": "2026-06-05"}]',
        encoding="utf-8",
    )
    exposicoes = carregar_exposicoes(arquivo)
    assert exposicoes[0].valor == Decimal("98000.50")


def test_id_duplicado_levanta_resposta_invalida(tmp_path):
    arquivo = tmp_path / "exposicoes.json"
    arquivo.write_text(
        '[{"id": "1", "tipo": "payable", "moeda": "USD", "valor": "1000", '
        '"vencimento": "2026-06-05"}, '
        '{"id": "1", "tipo": "receivable", "moeda": "EUR", "valor": "2000", '
        '"vencimento": "2026-06-08"}]',
        encoding="utf-8",
    )
    with pytest.raises(RespostaInvalida, match="duplicado"):
        carregar_exposicoes(arquivo)
