"""Schema SQLAlchemy Core das tabelas de persistência.

``consolidacao``: estado "atual" idempotente (1 linha por chave natural
``data_referencia + hash_conjunto``, UPSERT). ``consolidacao_historico``:
trilha append-only (1 linha por processamento, nunca atualizada).
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

consolidacao = Table(
    "consolidacao",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("data_referencia", Date, nullable=False),
    Column("hash_conjunto", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("criado_em", DateTime, nullable=False),
    Column("atualizado_em", DateTime, nullable=False),
    Column("num_processamentos", Integer, nullable=False),
    UniqueConstraint("data_referencia", "hash_conjunto", name="uq_consolidacao_run"),
)

consolidacao_historico = Table(
    "consolidacao_historico",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("data_referencia", Date, nullable=False),
    Column("hash_conjunto", String(64), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("processado_em", DateTime, nullable=False),
    Column("num_processamento", Integer, nullable=False),
)


def criar_schema(engine: Engine) -> None:
    """Cria as tabelas se não existirem."""
    metadata.create_all(engine)
