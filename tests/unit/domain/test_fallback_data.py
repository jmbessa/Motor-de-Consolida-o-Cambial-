"""Testes da regra de fallback de data (requisito 6.10)."""

from datetime import date

import pytest
from pydantic import ValidationError

from motor_cambial.domain.errors import SemCotacaoNaJanela
from motor_cambial.domain.rules.fallback_data import (
    ResultadoFallback,
    resolver_data_efetiva,
)


def test_data_exata_disponivel_sem_fallback():
    resultado = resolver_data_efetiva(
        data_solicitada=date(2026, 6, 5),
        datas_disponiveis={date(2026, 6, 5), date(2026, 6, 4)},
    )
    assert resultado.data_efetiva == date(2026, 6, 5)
    assert resultado.houve_fallback is False
    assert resultado.defasagem_dias == 0


def test_recua_para_a_data_disponivel_mais_recente():
    # Ex.: data solicitada cai num fim de semana; só a sexta anterior tem cotação.
    resultado = resolver_data_efetiva(
        data_solicitada=date(2026, 6, 7),
        datas_disponiveis={date(2026, 6, 5)},
    )
    assert resultado.data_efetiva == date(2026, 6, 5)
    assert resultado.houve_fallback is True
    assert resultado.defasagem_dias == 2


def test_feriado_prolongado_no_limite_da_janela():
    # defasagem de exatamente 7 dias — o limite é inclusive.
    resultado = resolver_data_efetiva(
        data_solicitada=date(2026, 6, 10),
        datas_disponiveis={date(2026, 6, 3)},
        janela_dias=7,
    )
    assert resultado.data_efetiva == date(2026, 6, 3)
    assert resultado.houve_fallback is True
    assert resultado.defasagem_dias == 7


def test_janela_estourada_levanta_erro_rastreavel():
    with pytest.raises(SemCotacaoNaJanela):
        resolver_data_efetiva(
            data_solicitada=date(2026, 6, 10),
            datas_disponiveis={date(2026, 6, 1)},  # 9 dias antes, fora da janela default
            janela_dias=7,
        )


def test_janela_configuravel_mais_curta():
    with pytest.raises(SemCotacaoNaJanela):
        resolver_data_efetiva(
            data_solicitada=date(2026, 6, 10),
            datas_disponiveis={date(2026, 6, 5)},  # 5 dias antes
            janela_dias=3,
        )


def test_nunca_usa_data_futura():
    # Só datas <= data_solicitada podem ser candidatas.
    resultado = resolver_data_efetiva(
        data_solicitada=date(2026, 6, 5),
        datas_disponiveis={date(2026, 6, 6), date(2026, 6, 4)},
    )
    assert resultado.data_efetiva == date(2026, 6, 4)


def test_resultado_fallback_e_imutavel():
    resultado = ResultadoFallback(
        data_efetiva=date(2026, 6, 5), houve_fallback=False, defasagem_dias=0
    )
    with pytest.raises(Exception):
        resultado.defasagem_dias = 5


def test_janela_negativa_e_rejeitada():
    with pytest.raises(ValueError):
        resolver_data_efetiva(
            data_solicitada=date(2026, 6, 5),
            datas_disponiveis={date(2026, 6, 5)},
            janela_dias=-1,
        )


def test_datas_disponiveis_vazio_levanta_erro():
    with pytest.raises(SemCotacaoNaJanela):
        resolver_data_efetiva(
            data_solicitada=date(2026, 6, 5),
            datas_disponiveis=set(),
        )


def test_resultado_fallback_rejeita_incoerencia_fallback_true_com_defasagem_zero():
    with pytest.raises(ValidationError):
        ResultadoFallback(
            data_efetiva=date(2026, 6, 5), houve_fallback=True, defasagem_dias=0
        )


def test_resultado_fallback_rejeita_incoerencia_fallback_false_com_defasagem_positiva():
    with pytest.raises(ValidationError):
        ResultadoFallback(
            data_efetiva=date(2026, 6, 5), houve_fallback=False, defasagem_dias=9
        )
