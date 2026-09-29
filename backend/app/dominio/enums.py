"""Vocabularios del modelo de datos (seccion "Dominios y transiciones usados por UML").

Se declaran como StrEnum: viajan como texto en la API y se guardan como texto en la base.
Un tipo ENUM de PostgreSQL obligaria a una migracion por cada valor nuevo.
"""

from enum import StrEnum


class VisibilidadPerfil(StrEnum):
    PUBLICO = "PUBLICO"
    PRIVADO = "PRIVADO"


class FuncionRepresentante(StrEnum):
    GESTOR_RETOS = "GESTOR_RETOS"
    REVOCADOR = "REVOCADOR"
    GESTOR_Y_REVOCADOR = "GESTOR_Y_REVOCADOR"

    def puede_gestionar_retos(self) -> bool:
        return self in (FuncionRepresentante.GESTOR_RETOS, FuncionRepresentante.GESTOR_Y_REVOCADOR)

    def puede_revocar(self) -> bool:
        return self in (FuncionRepresentante.REVOCADOR, FuncionRepresentante.GESTOR_Y_REVOCADOR)


class EstadoPreparacion(StrEnum):
    RECIBIDA = "RECIBIDA"
    PROCESANDO = "PROCESANDO"
    LISTA = "LISTA"
    ERROR = "ERROR"


class EstadoReto(StrEnum):
    BORRADOR = "BORRADOR"
    PUBLICADO = "PUBLICADO"
    CERRADO = "CERRADO"


class CategoriaPrueba(StrEnum):
    FUNCIONAL = "FUNCIONAL"
    CASO_LIMITE = "CASO_LIMITE"
    RENDIMIENTO = "RENDIMIENTO"


class EstadoEvaluacion(StrEnum):
    PENDIENTE = "PENDIENTE"
    EN_EJECUCION = "EN_EJECUCION"
    FINALIZADA = "FINALIZADA"
    ERROR_TECNICO = "ERROR_TECNICO"


class Dictamen(StrEnum):
    APROBADO = "APROBADO"
    NO_APROBADO = "NO_APROBADO"
    # Ninguna comprobacion obligatoria llego a ejecutarse (p. ej. el reto no define su codigo).
    # No es un veredicto sobre la solucion: no aprueba, pero tampoco se presenta como desaprobacion.
    NO_EVALUABLE = "NO_EVALUABLE"


class CondicionEjecucion(StrEnum):
    EJECUTADA = "EJECUTADA"
    NO_EJECUTADA = "NO_EJECUTADA"
    ERROR_TECNICO = "ERROR_TECNICO"


class ResultadoOperacion(StrEnum):
    EXITO = "EXITO"
    DENEGADA = "DENEGADA"
    ERROR = "ERROR"


class OrigenEvento(StrEnum):
    USUARIO = "USUARIO"
    SISTEMA = "SISTEMA"


class CondicionParticipacion(StrEnum):
    """Siempre derivada de las credenciales; nunca se persiste (RN-CRED-04)."""

    EN_PROGRESO = "EN_PROGRESO"
    CERTIFICADA = "CERTIFICADA"
    REQUIERE_RECERTIFICACION = "REQUIERE_RECERTIFICACION"
