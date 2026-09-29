import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.dominio.enums import (
    CondicionEjecucion,
    CondicionParticipacion,
    Dictamen,
    EstadoEvaluacion,
)


class ParticipacionSalida(BaseModel):
    id: uuid.UUID
    reto_id: uuid.UUID
    titulo_reto: str
    momento_incorporacion: datetime
    repositorio_base: str | None = None
    version_base: str | None = None
    # Propiedad derivada: no existe como columna (RN-CRED-04).
    condicion_certificacion: CondicionParticipacion
    admite_entrega: bool


class EntregaEntrada(BaseModel):
    repositorio: str = Field(min_length=4, max_length=500)
    commit: str = Field(min_length=6, max_length=64)


class EntregaSalida(BaseModel):
    id: uuid.UUID
    participacion_id: uuid.UUID
    numero_intento: int
    momento_entrega: datetime
    repositorio: str
    commit: str
    huella_proyecto: str | None = None
    evaluaciones: list[uuid.UUID] = []


class EvaluacionAceptada(BaseModel):
    evaluacion_id: uuid.UUID
    entrega_id: uuid.UUID
    estado_procesamiento: EstadoEvaluacion
    consultar_en: str


class ResultadoPruebaSalida(BaseModel):
    prueba_id: uuid.UUID
    prueba: str
    categoria: str
    obligatoria: bool
    condicion_ejecucion: CondicionEjecucion
    aprobada: bool | None = None
    valor_observado: float | None = None
    unidad: str | None = None
    duracion_ms: int | None = None
    detalle: str | None = None


class CredencialResumen(BaseModel):
    identificador_publico: str
    vigente: bool
    url_verificacion: str


class EvaluacionSalida(BaseModel):
    id: uuid.UUID
    entrega_id: uuid.UUID
    estado_procesamiento: EstadoEvaluacion
    momento_solicitud: datetime
    momento_inicio: datetime | None = None
    momento_fin: datetime | None = None
    # La version del evaluador viaja siempre: quien lea el resultado sabe que lo produjo.
    version_evaluador: str
    dictamen: Dictamen | None = None
    detalle_error: str | None = None
    progreso: dict | None = None
    resultados: list[ResultadoPruebaSalida] = []
    credencial: CredencialResumen | None = None
    # Juez IA: se completa al finalizar. No forma parte del dictamen.
    revision_ia: dict | None = None
