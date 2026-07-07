"""Testes do contrato do port de cotação."""

from datetime import date

from motor_cambial.domain.enums import Fonte, Moeda
from motor_cambial.domain.models import CotacaoNormalizada
from motor_cambial.ports.cotacao_provider import CotacaoProvider


class _ProviderFake:
    fonte = Fonte.FRANKFURTER

    def buscar_cotacoes(
        self, moeda: Moeda, data_inicial: date, data_final: date
    ) -> list[CotacaoNormalizada]:
        return []


def test_stub_conforme_e_reconhecido_como_provider():
    assert isinstance(_ProviderFake(), CotacaoProvider)


def test_objeto_sem_metodo_nao_e_provider():
    class SemMetodo:
        fonte = Fonte.PTAX

    assert not isinstance(SemMetodo(), CotacaoProvider)
