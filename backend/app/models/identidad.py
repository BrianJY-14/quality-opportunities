import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.dominio.enums import FuncionRepresentante, VisibilidadPerfil
from app.models._base import IdentificadorPropio, ahora
from app.models._tipos import MomentoUTC


class Usuario(IdentificadorPropio, Base):
    """RN-ID-01: un usuario tiene como maximo un perfil estudiante y puede representar
    varias organizaciones. Ambas condiciones son compatibles, asi que NO hay rol global."""

    __tablename__ = "usuario"

    nombre: Mapped[str] = mapped_column(String(255))
    correo: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hash_password: Mapped[str] = mapped_column(String(255))
    momento_alta: Mapped[datetime] = mapped_column(MomentoUTC, default=ahora)

    perfil: Mapped["PerfilEstudiante | None"] = relationship(
        back_populates="usuario", uselist=False, cascade="all, delete-orphan"
    )
    representaciones: Mapped[list["Representacion"]] = relationship(back_populates="usuario")


class PerfilEstudiante(Base):
    """Identidad dependiente: se identifica por su usuario."""

    __tablename__ = "perfil_estudiante"

    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuario.id"), primary_key=True)
    nombre_publico: Mapped[str] = mapped_column(String(255))
    biografia: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibilidad: Mapped[str] = mapped_column(String(16), default=VisibilidadPerfil.PUBLICO)
    universidad: Mapped[str | None] = mapped_column(String(255), nullable=True)
    carrera: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ciclo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Resumen profesional redactado por el LLM a partir de la evidencia verificada del perfil.
    resumen_ia: Mapped[str | None] = mapped_column(Text, nullable=True)
    momento_resumen: Mapped[datetime | None] = mapped_column(MomentoUTC, nullable=True)

    usuario: Mapped[Usuario] = relationship(back_populates="perfil")
    participaciones: Mapped[list["Participacion"]] = relationship(back_populates="perfil")  # noqa: F821


class Organizacion(IdentificadorPropio, Base):
    """Tambien permite que la plataforma sea responsable de un reto de demostracion."""

    __tablename__ = "organizacion"

    nombre: Mapped[str] = mapped_column(String(255), unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    sitio_web: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo: Mapped[str | None] = mapped_column(String(500), nullable=True)

    representaciones: Mapped[list["Representacion"]] = relationship(back_populates="organizacion")


class Representacion(Base):
    """Quien puede actuar por una organizacion. Identidad dependiente: pareja usuario-organizacion.

    Finalizarla conserva el registro y su autoria historica (seccion 3 del diseno)."""

    __tablename__ = "representacion"

    usuario_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("usuario.id"), primary_key=True)
    organizacion_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizacion.id"), primary_key=True)
    funcion_autorizada: Mapped[str] = mapped_column(String(24), default=FuncionRepresentante.GESTOR_RETOS)
    momento_inicio: Mapped[datetime] = mapped_column(MomentoUTC, default=ahora)
    momento_fin: Mapped[datetime | None] = mapped_column(MomentoUTC, nullable=True)

    usuario: Mapped[Usuario] = relationship(back_populates="representaciones")
    organizacion: Mapped[Organizacion] = relationship(back_populates="representaciones")

    def esta_activa(self, en: datetime) -> bool:
        return self.momento_inicio <= en and (self.momento_fin is None or en < self.momento_fin)
