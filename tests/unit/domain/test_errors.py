"""Testes das exceções de domínio."""

import pytest

from motor_cambial.domain.errors import (
    DomainError,
    SemCotacaoNaJanela,
    TipoNaoSuportado,
    ValorForaDeFaixa,
)


def test_sem_cotacao_na_janela_e_domain_error():
    assert issubclass(SemCotacaoNaJanela, DomainError)
    with pytest.raises(DomainError):
        raise SemCotacaoNaJanela("sem cotação")


def test_valor_fora_de_faixa_e_domain_error():
    assert issubclass(ValorForaDeFaixa, DomainError)
    with pytest.raises(ValorForaDeFaixa):
        raise ValorForaDeFaixa("fora de faixa")


def test_domain_error_e_exception():
    assert issubclass(DomainError, Exception)


def test_tipo_nao_suportado_e_domain_error():
    assert issubclass(TipoNaoSuportado, DomainError)


from motor_cambial.domain.errors import (
    FonteIndisponivel,
    MoedaNaoSuportadaPelaFonte,
    RespostaInvalida,
)


def test_fonte_indisponivel_e_domain_error():
    assert issubclass(FonteIndisponivel, DomainError)


def test_resposta_invalida_e_domain_error():
    assert issubclass(RespostaInvalida, DomainError)


def test_moeda_nao_suportada_pela_fonte_e_domain_error():
    assert issubclass(MoedaNaoSuportadaPelaFonte, DomainError)


def test_persistencia_indisponivel_e_domain_error():
    from motor_cambial.domain.errors import DomainError, PersistenciaIndisponivel

    assert issubclass(PersistenciaIndisponivel, DomainError)
