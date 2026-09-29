from app.models.auditoria import EventoAuditoria
from app.models.credencial import Credencial, RevocacionCredencial
from app.models.evaluacion import Entrega, Evaluacion, Participacion, ResultadoPrueba
from app.models.ia import Defensa, RevisionIA
from app.models.identidad import Organizacion, PerfilEstudiante, Representacion, Usuario
from app.models.reto import Prueba, Reto, SolicitudReto
from app.models.workspace import EspacioTrabajo

__all__ = [
    "Usuario",
    "PerfilEstudiante",
    "Organizacion",
    "Representacion",
    "SolicitudReto",
    "Reto",
    "Prueba",
    "Participacion",
    "EspacioTrabajo",
    "Entrega",
    "Evaluacion",
    "ResultadoPrueba",
    "Credencial",
    "RevocacionCredencial",
    "EventoAuditoria",
    "RevisionIA",
    "Defensa",
]
