import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.dominio.enums import CondicionEjecucion, EstadoEvaluacion
from app.models._base import IdentificadorPropio, ahora
from app.models._tipos import MomentoUTC


class Participacion(IdentificadorPropio, Base):
    """RN-PART-01: un perfil tiene como maximo una participacion por reto."""

    __tablename__ = "participacion"
    __table_args__ = (UniqueConstraint("perfil_usuario_id", "reto_id", name="uq_participacion_perfil_reto"),)

    perfil_usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("perfil_estudiante.usuario_id"))
    reto_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("reto.id"))
    momento_incorporacion: Mapped[datetime] = mapped_column(MomentoUTC, default=ahora)

    perfil: Mapped["PerfilEstudiante"] = relationship(back_populates="participaciones")  # noqa: F821
    reto: Mapped["Reto"] = relationship(lazy="joined")  # noqa: F821
    entregas: Mapped[list["Entrega"]] = relationship(back_populates="participacion")
    credenciales: Mapped[list["Credencial"]] = relationship(back_populates="participacion")  # noqa: F821


class Entrega(IdentificadorPropio, Base):
    """RN-PART-02: identifica repositorio, commit e intento. El codigo no se cambia
    despues de recibir una evaluacion."""

    __tablename__ = "entrega"
    __table_args__ = (UniqueConstraint("participacion_id", "numero_intento", name="uq_entrega_intento"),)

    participacion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("participacion.id"))
    numero_intento: Mapped[int] = mapped_column(Integer, default=1)
    momento_entrega: Mapped[datetime] = mapped_column(MomentoUTC, default=ahora)
    repositorio: Mapped[str] = mapped_column(String(500))
    commit: Mapped[str] = mapped_column(String(64))
    # Copia congelada del espacio de trabajo al enviar (regla 4 del procedimiento) y su SHA-256
    # sobre el documento canonico. Seguir editando el borrador no altera lo entregado.
    proyecto: Mapped[str | None] = mapped_column(Text, nullable=True)
    huella_proyecto: Mapped[str | None] = mapped_column(String(64), nullable=True)

    participacion: Mapped[Participacion] = relationship(back_populates="entregas")
    evaluaciones: Mapped[list["Evaluacion"]] = relationship(back_populates="entrega")


class Evaluacion(IdentificadorPropio, Base):
    """RN-EVAL-01: una entrega puede recibir MUCHAS evaluaciones, cada una con su propio
    inicio, fin, version del evaluador y resultado. Reevaluar no exige una entrega nueva.

    Fusiona lo que antes eran ejecucion y veredicto: no hay un dictamen unico mutable por entrega.
    """

    __tablename__ = "evaluacion"

    entrega_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("entrega.id"))
    estado_procesamiento: Mapped[str] = mapped_column(String(16), default=EstadoEvaluacion.PENDIENTE)
    momento_solicitud: Mapped[datetime] = mapped_column(MomentoUTC, default=ahora)
    momento_inicio: Mapped[datetime | None] = mapped_column(MomentoUTC, nullable=True)
    momento_fin: Mapped[datetime | None] = mapped_column(MomentoUTC, nullable=True)
    version_evaluador: Mapped[str] = mapped_column(String(60))
    # Ausente mientras no exista un dictamen valido, incluido el error de infraestructura.
    dictamen: Mapped[str | None] = mapped_column(String(16), nullable=True)
    detalle_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    entrega: Mapped[Entrega] = relationship(back_populates="evaluaciones")
    resultados: Mapped[list["ResultadoPrueba"]] = relationship(
        back_populates="evaluacion", cascade="all, delete-orphan"
    )


class ResultadoPrueba(Base):
    """RN-EVAL-02: como maximo un resultado por pareja evaluacion-prueba.

    La identidad dependiente lo garantiza sin restriccion adicional."""

    __tablename__ = "resultado_prueba"

    evaluacion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("evaluacion.id"), primary_key=True)
    prueba_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("prueba.id"), primary_key=True)
    condicion_ejecucion: Mapped[str] = mapped_column(String(16), default=CondicionEjecucion.EJECUTADA)
    # Solo se informa para una comprobacion efectivamente ejecutada.
    aprobada: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    valor_observado: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    unidad: Mapped[str | None] = mapped_column(String(24), nullable=True)
    duracion_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)

    evaluacion: Mapped[Evaluacion] = relationship(back_populates="resultados")
    prueba: Mapped["Prueba"] = relationship(lazy="joined")  # noqa: F821

    def es_aprobado(self) -> bool:
        return self.condicion_ejecucion == CondicionEjecucion.EJECUTADA and bool(self.aprobada)
