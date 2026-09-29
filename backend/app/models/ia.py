"""Resultados de las funciones de IA que se conservan como evidencia.

- `RevisionIA`: el juez de codigo. Una por evaluacion, identidad dependiente. Se calcula tras el
  dictamen y NO lo altera: la aprobacion depende solo de la bateria oficial (regla 17 del
  procedimiento). La revision aporta calidad al CV y al ranking.
- `Defensa`: entrevista tecnica sobre el codigo entregado. Varias por entrega (se puede reintentar);
  las preguntas se generan a partir de ese codigo y las respuestas las califica el modelo.

Los campos JSON se guardan como texto: son documentos que se leen enteros y nunca se consultan
por dentro, y un tipo JSON especifico de PostgreSQL rompe la paridad con SQLite en las pruebas.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._base import IdentificadorPropio, ahora
from app.models._tipos import MomentoUTC


class RevisionIA(Base):
    __tablename__ = "revision_ia"

    evaluacion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("evaluacion.id"), primary_key=True)
    # COMPLETADA: con modelo. SOLO_ESTATICA: sin modelo disponible, solo metricas deterministas.
    # SIN_CODIGO: la entrega no trae proyecto que revisar.
    estado: Mapped[str] = mapped_column(String(16))
    modelo: Mapped[str] = mapped_column(String(120))
    version_instrucciones: Mapped[str] = mapped_column(String(40))
    momento: Mapped[datetime] = mapped_column(MomentoUTC, default=ahora)
    huella_proyecto: Mapped[str | None] = mapped_column(String(64), nullable=True)
    puntaje_global: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dimensiones: Mapped[str] = mapped_column(Text, default="{}")
    aptitudes: Mapped[str] = mapped_column(Text, default="[]")
    fortalezas: Mapped[str] = mapped_column(Text, default="[]")
    mejoras: Mapped[str] = mapped_column(Text, default="[]")
    analisis_estatico: Mapped[str] = mapped_column(Text, default="{}")
    resumen: Mapped[str | None] = mapped_column(Text, nullable=True)

    evaluacion: Mapped["Evaluacion"] = relationship()  # noqa: F821


class Defensa(IdentificadorPropio, Base):
    __tablename__ = "defensa"

    entrega_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("entrega.id"), index=True)
    # PENDIENTE: preguntas generadas, sin respuestas. CALIFICADA: con puntaje del modelo.
    # SIN_CALIFICAR: respuestas guardadas pero no habia modelo para evaluarlas.
    estado: Mapped[str] = mapped_column(String(16), default="PENDIENTE")
    modelo: Mapped[str] = mapped_column(String(120))
    momento_creacion: Mapped[datetime] = mapped_column(MomentoUTC, default=ahora)
    momento_respuesta: Mapped[datetime | None] = mapped_column(MomentoUTC, nullable=True)
    # [{"id", "pregunta", "enfoque", "archivo"}] visibles al estudiante, y la rubrica privada aparte.
    preguntas: Mapped[str] = mapped_column(Text)
    rubrica_privada: Mapped[str] = mapped_column(Text, default="[]")
    respuestas: Mapped[str | None] = mapped_column(Text, nullable=True)
    calificaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    puntaje: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aprobada: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    retroalimentacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    entrega: Mapped["Entrega"] = relationship()  # noqa: F821
