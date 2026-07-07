"""Exceções de domínio (puras — sem I/O)."""


class DomainError(Exception):
    """Erro de negócio do domínio cambial."""


class SemCotacaoNaJanela(DomainError):
    """Nenhuma cotação disponível dentro da janela de fallback configurada."""


class ValorForaDeFaixa(DomainError):
    """Valor monetário fora da faixa suportada para a operação solicitada."""


class TipoNaoSuportado(DomainError):
    """Um tipo (enum) não foi tratado explicitamente por uma regra — rede de segurança."""
