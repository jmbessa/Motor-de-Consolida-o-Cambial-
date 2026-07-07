"""Adapter MySQL do port ResultadoRepository (SQLAlchemy Core + PyMySQL).

``salvar`` faz, numa transação: UPSERT na tabela ``consolidacao`` (chave
natural; ``criado_em`` preservado, ``atualizado_em``/``num_processamentos``
avançam) e um INSERT na ``consolidacao_historico`` (append-only). O payload
é o ``ResultadoConsolidacao`` serializado de forma lossless
(``model_dump(mode="json")`` — Decimal como string). Timestamps em UTC.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from pydantic import ValidationError
from sqlalchemy import insert, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from motor_cambial.adapters.outbound.persistence.schema import (
    consolidacao,
    consolidacao_historico,
)
from motor_cambial.domain.errors import PersistenciaIndisponivel, RespostaInvalida
from motor_cambial.domain.resultado_consolidacao import (
    RegistroHistorico,
    ResultadoConsolidacao,
)


class RepositorioResultadoSQL:
    """Implementa ResultadoRepository sobre MySQL."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def salvar(self, resultado: ResultadoConsolidacao) -> None:
        payload = resultado.model_dump(mode="json")
        agora = datetime.now(timezone.utc).replace(microsecond=0)
        try:
            with self._engine.begin() as conn:
                stmt = mysql_insert(consolidacao).values(
                    data_referencia=resultado.data_referencia,
                    hash_conjunto=resultado.hash_conjunto,
                    payload=payload,
                    criado_em=agora,
                    atualizado_em=agora,
                    num_processamentos=1,
                )
                stmt = stmt.on_duplicate_key_update(
                    payload=stmt.inserted.payload,
                    atualizado_em=stmt.inserted.atualizado_em,
                    num_processamentos=consolidacao.c.num_processamentos + 1,
                )
                conn.execute(stmt)
                num = conn.execute(
                    select(consolidacao.c.num_processamentos).where(
                        consolidacao.c.data_referencia == resultado.data_referencia,
                        consolidacao.c.hash_conjunto == resultado.hash_conjunto,
                    )
                ).scalar_one()
                conn.execute(
                    insert(consolidacao_historico).values(
                        data_referencia=resultado.data_referencia,
                        hash_conjunto=resultado.hash_conjunto,
                        payload=payload,
                        processado_em=agora,
                        num_processamento=num,
                    )
                )
        except SQLAlchemyError as exc:
            raise PersistenciaIndisponivel(
                f"falha ao persistir consolidação: {exc}"
            ) from exc

    def buscar(
        self, data_referencia: date, hash_conjunto: str
    ) -> ResultadoConsolidacao | None:
        try:
            with self._engine.connect() as conn:
                row = conn.execute(
                    select(consolidacao.c.payload).where(
                        consolidacao.c.data_referencia == data_referencia,
                        consolidacao.c.hash_conjunto == hash_conjunto,
                    )
                ).scalar_one_or_none()
        except SQLAlchemyError as exc:
            raise PersistenciaIndisponivel(f"falha ao ler consolidação: {exc}") from exc
        if row is None:
            return None
        return self._desserializar(row)

    def buscar_historico(
        self, data_referencia: date, hash_conjunto: str
    ) -> tuple[RegistroHistorico, ...]:
        try:
            with self._engine.connect() as conn:
                linhas = conn.execute(
                    select(
                        consolidacao_historico.c.payload,
                        consolidacao_historico.c.processado_em,
                        consolidacao_historico.c.num_processamento,
                    )
                    .where(
                        consolidacao_historico.c.data_referencia == data_referencia,
                        consolidacao_historico.c.hash_conjunto == hash_conjunto,
                    )
                    .order_by(consolidacao_historico.c.num_processamento)
                ).all()
        except SQLAlchemyError as exc:
            raise PersistenciaIndisponivel(f"falha ao ler histórico: {exc}") from exc
        return tuple(
            RegistroHistorico(
                resultado=self._desserializar(linha.payload),
                processado_em=linha.processado_em.replace(tzinfo=timezone.utc),
                num_processamento=linha.num_processamento,
            )
            for linha in linhas
        )

    @staticmethod
    def _desserializar(payload: object) -> ResultadoConsolidacao:
        try:
            return ResultadoConsolidacao.model_validate(payload)
        except ValidationError as exc:
            raise RespostaInvalida(
                f"payload de consolidação gravado é inválido: {exc}"
            ) from exc
