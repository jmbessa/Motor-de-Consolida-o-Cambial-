"""Testes de integração que batem nas APIs reais (opt-in: -m integration)."""

from datetime import date
from decimal import Decimal

import pytest

from motor_cambial.composition_root import construir_providers
from motor_cambial.config import Config
from motor_cambial.domain.enums import Fonte, Moeda

pytestmark = pytest.mark.integration

_INI = date(2026, 6, 1)
_FIM = date(2026, 6, 8)


@pytest.fixture
def providers(tmp_path):
    return construir_providers(Config(cache_dir=tmp_path, modo_live=True))


def test_frankfurter_real_retorna_cotacoes(providers):
    cotacoes = providers[Fonte.FRANKFURTER].buscar_cotacoes(Moeda.USD, _INI, _FIM)
    assert cotacoes
    assert all(c.taxa_compra > Decimal("0") for c in cotacoes)
    assert all(c.possui_spread is False for c in cotacoes)


def test_ptax_real_retorna_cotacoes_com_spread(providers):
    cotacoes = providers[Fonte.PTAX].buscar_cotacoes(Moeda.USD, _INI, _FIM)
    assert cotacoes
    assert all(c.taxa_venda >= c.taxa_compra for c in cotacoes)
    assert all(c.timestamp is not None for c in cotacoes)
