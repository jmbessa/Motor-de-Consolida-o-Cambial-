"""Testes da regra de identidade de run (hash do conjunto de exposições)."""

from datetime import date

from motor_cambial.domain.enums import Moeda, TipoExposicao
from motor_cambial.domain.models import Exposicao
from motor_cambial.domain.rules.idempotencia import hash_do_conjunto


def _exp(id="1", tipo=TipoExposicao.PAYABLE, moeda=Moeda.USD, valor="125000",
         vencimento=date(2026, 6, 5), descricao=""):
    return Exposicao(id=id, tipo=tipo, moeda=moeda, valor=valor,
                     vencimento=vencimento, descricao=descricao)


def test_hash_e_hex_de_64_chars():
    h = hash_do_conjunto([_exp()])
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_determinismo_mesma_lista_mesmo_hash():
    lista = [_exp(id="1"), _exp(id="2", moeda=Moeda.EUR)]
    assert hash_do_conjunto(lista) == hash_do_conjunto(lista)


def test_independente_de_ordem():
    a, b = _exp(id="1"), _exp(id="2", moeda=Moeda.EUR)
    assert hash_do_conjunto([a, b]) == hash_do_conjunto([b, a])


def test_valor_por_valor_ignora_escala():
    # 125000 e 125000.00 são o mesmo valor econômico -> mesmo hash.
    assert hash_do_conjunto([_exp(valor="125000")]) == hash_do_conjunto(
        [_exp(valor="125000.00")]
    )


def test_descricao_diferente_nao_muda_hash():
    assert hash_do_conjunto([_exp(descricao="AWS")]) == hash_do_conjunto(
        [_exp(descricao="Amazon Web Services")]
    )


def test_mudar_valor_muda_hash():
    assert hash_do_conjunto([_exp(valor="125000")]) != hash_do_conjunto(
        [_exp(valor="125001")]
    )


def test_mudar_tipo_muda_hash():
    assert hash_do_conjunto([_exp(tipo=TipoExposicao.PAYABLE)]) != hash_do_conjunto(
        [_exp(tipo=TipoExposicao.RECEIVABLE)]
    )


def test_mudar_moeda_muda_hash():
    assert hash_do_conjunto([_exp(moeda=Moeda.USD)]) != hash_do_conjunto(
        [_exp(moeda=Moeda.EUR)]
    )


def test_mudar_vencimento_muda_hash():
    assert hash_do_conjunto([_exp(vencimento=date(2026, 6, 5))]) != hash_do_conjunto(
        [_exp(vencimento=date(2026, 6, 6))]
    )


def test_mudar_id_muda_hash():
    assert hash_do_conjunto([_exp(id="1")]) != hash_do_conjunto([_exp(id="2")])


def test_ids_com_caracteres_especiais_nao_colidem():
    # A canonização não pode colidir por concatenação ingênua de campos.
    a = _exp(id='a"|,:b')
    b = _exp(id="a", descricao="")
    assert hash_do_conjunto([a]) != hash_do_conjunto([b])


def test_conjunto_vazio_tem_hash_estavel():
    assert hash_do_conjunto([]) == hash_do_conjunto([])
    assert len(hash_do_conjunto([])) == 64
