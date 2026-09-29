import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.dominio.enums import CategoriaPrueba, EstadoPreparacion, EstadoReto
from app.models._base import IdentificadorPropio, ahora
from app.models._tipos import MomentoUTC
from app.models.identidad import Organizacion  # noqa: F401


class SolicitudReto(IdentificadorPropio, Base):
    """RN-ING-01: el original y los detalles de preparacion son privados.

    RN-ING-03: guarda la procedencia de la preparacion aceptada; no un historial de ejecuciones.
    """

    __tablename__ = "solicitud_reto"
    __table_args__ = (
        # La autoria se obtiene de la representacion (RN-ORG-01), no de un usuario suelto.
        ForeignKeyConstraint(
            ["representante_usuario_id", "organizacion_id"],
            ["representacion.usuario_id", "representacion.organizacion_id"],
        ),
    )

    representante_usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    organizacion_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    titulo_original: Mapped[str] = mapped_column(String(500))
    contenido_original_restringido: Mapped[str | None] = mapped_column(Text, nullable=True)
    momento_recepcion: Mapped[datetime] = mapped_column(MomentoUTC, default=ahora)
    estado_preparacion: Mapped[str] = mapped_column(String(16), default=EstadoPreparacion.RECIBIDA)
    modelo_ia: Mapped[str | None] = mapped_column(String(120), nullable=True)
    version_instrucciones: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resumen_preparacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    detalle_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    retos: Mapped[list["Reto"]] = relationship(back_populates="solicitud")


class Reto(IdentificadorPropio, Base):
    __tablename__ = "reto"

    organizacion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizacion.id"))
    # Un reto puede no tener solicitud si es un caso publico preparado por la organizacion.
    solicitud_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("solicitud_reto.id"), nullable=True)
    titulo: Mapped[str] = mapped_column(String(500))
    descripcion_publica: Mapped[str] = mapped_column(Text, default="")
    criterios_aceptacion: Mapped[str] = mapped_column(Text, default="")
    estado: Mapped[str] = mapped_column(String(16), default=EstadoReto.BORRADOR)
    momento_publicacion: Mapped[datetime | None] = mapped_column(MomentoUTC, nullable=True)
    momento_cierre: Mapped[datetime | None] = mapped_column(MomentoUTC, nullable=True)
    repositorio_base: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version_base: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # BASICO | INTERMEDIO | AVANZADO. Pondera la experiencia que aporta el reto al ranking.
    dificultad: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Lista JSON de aptitudes que ejercita el reto; alimenta el grafo de aptitudes del CV.
    aptitudes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Documento JSON `{"version", "archivos"}` con el proyecto inicial del editor.
    proyecto_base: Mapped[str | None] = mapped_column(Text, nullable=True)

    organizacion: Mapped[Organizacion] = relationship(lazy="joined")
    solicitud: Mapped[SolicitudReto | None] = relationship(back_populates="retos")
    pruebas: Mapped[list["Prueba"]] = relationship(back_populates="reto", cascade="all, delete-orphan")

    def admite_entregas(self) -> bool:
        """RN-EVAL-04: cerrar bloquea nuevas entregas e inicios."""
        return self.estado == EstadoReto.PUBLICADO


class Prueba(IdentificadorPropio, Base):
    """Comprobacion sobre la solucion del estudiante. Cada reto tiene un conjunto fijo,
    sin suites con ciclo propio."""

    __tablename__ = "prueba"

    reto_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("reto.id"))
    nombre: Mapped[str] = mapped_column(String(300))
    categoria: Mapped[str] = mapped_column(String(16), default=CategoriaPrueba.FUNCIONAL)
    obligatoria: Mapped[bool] = mapped_column(Boolean, default=False)
    condicion_aprobacion: Mapped[str] = mapped_column(Text, default="")
    limite_ejecucion_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    referencia_ejecutable: Mapped[str] = mapped_column(String(300), default="")
    # El codigo de la comprobacion oficial, propiedad del reto y NO del estudiante. El evaluador
    # lo escribe en una carpeta del sandbox aparte del proyecto entregado: si la prueba viniera
    # del proyecto, bastaria con entregar una que apruebe siempre. Vacio = sin comprobacion
    # ejecutable, y entonces la prueba queda NO_EJECUTADA en vez de dar un veredicto falso.
    contenido_ejecutable: Mapped[str | None] = mapped_column(Text, nullable=True)

    reto: Mapped[Reto] = relationship(back_populates="pruebas")
