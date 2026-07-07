"""Exceções de domínio (puras — sem I/O)."""


class DomainError(Exception):
    """Erro de negócio do domínio cambial."""


class SemCotacaoNaJanela(DomainError):
    """Nenhuma cotação disponível dentro da janela de fallback configurada."""


class ValorForaDeFaixa(DomainError):
    """Valor monetário fora da faixa suportada para a operação solicitada."""


class TipoNaoSuportado(DomainError):
    """Um tipo (enum) não foi tratado explicitamente por uma regra — rede de segurança."""


class FonteIndisponivel(DomainError):
    """Falha de transporte ao consultar uma fonte de cotação (timeout, 5xx, rede)."""


class RespostaInvalida(DomainError):
    """Resposta de uma fonte veio malformada ou incompleta."""


class MoedaNaoSuportadaPelaFonte(DomainError):
    """A fonte de cotação não fornece a moeda solicitada."""


class PersistenciaIndisponivel(DomainError):
    """Falha ao persistir/ler o resultado (conexão, transação, indisponibilidade do store)."""
