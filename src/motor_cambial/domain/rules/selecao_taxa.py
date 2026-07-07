"""Regra de seleção de taxa por tipo de exposição (requisitos 6.8 e 6.9).

O spread (diferença compra/venda) é a margem de quem intermedeia a
transação no mercado. A regra segue a direção do fluxo de caixa:

- payable -> VENDA: para liquidar, a empresa compra a moeda; é a taxa mais
  conservadora do ponto de vista da saída de caixa.
- receivable -> COMPRA: ao receber, a empresa vende a moeda; é a taxa
  coerente com a entrada de caixa esperada.
- intercompany -> REFERENCIA (mid): operação interna ao grupo não cruza o
  spread de mercado; premissa documentada, pois o enunciado não especifica
  uma regra para intercompany.
"""

from motor_cambial.domain.enums import TipoExposicao, TipoTaxa
from motor_cambial.domain.errors import TipoNaoSuportado


def tipo_taxa_para(tipo: TipoExposicao) -> TipoTaxa:
    """Retorna qual lado da cotação aplicar para o tipo de exposição."""
    tipo = TipoExposicao(tipo)  # normaliza e falha alto em valor inválido
    if tipo is TipoExposicao.PAYABLE:
        return TipoTaxa.VENDA
    if tipo is TipoExposicao.RECEIVABLE:
        return TipoTaxa.COMPRA
    if tipo is TipoExposicao.INTERCOMPANY:
        return TipoTaxa.REFERENCIA
    # Rede de segurança: TipoExposicao(tipo) já restringe aos 3 membros acima;
    # este raise só dispara se um novo membro for adicionado sem atualizar
    # esta função.
    raise TipoNaoSuportado(f"TipoExposicao não tratado em tipo_taxa_para: {tipo!r}")
