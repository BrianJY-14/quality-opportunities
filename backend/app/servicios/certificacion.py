"""ServicioCertificacion del UML.

Obtiene la participacion desde la evaluacion y emite con todas las precondiciones ante una
llamada interna autorizada. Consulta vigencia y revoca con autorizacion del actor. Registra
emision y reversa sin sobrescribirlas.
"""

import hashlib
import json
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, lazyload

from app.core.config import get_settings
from app.core.errors import ErrorDominio
from app.dominio.enums import (
    CondicionParticipacion,
    Dictamen,
    EstadoEvaluacion,
    OrigenEvento,
)
from app.models import Credencial, Evaluacion, Participacion, RevocacionCredencial, Usuario
from app.models._base import ahora
from app.servicios import auditoria

settings = get_settings()
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin caracteres que se confundan al dictar


def _identificador_publico(anio: int) -> str:
    return f"{settings.PREFIJO_CREDENCIAL}-{anio}-{''.join(secrets.choice(_ALFABETO) for _ in range(6))}"


def credenciales_de(db: Session, participacion_id: uuid.UUID) -> list[Credencial]:
    return list(
        db.scalars(
            select(Credencial)
            .where(Credencial.participacion_id == participacion_id)
            .order_by(Credencial.momento_emision.desc())
        ).all()
    )


def credencial_vigente(db: Session, participacion_id: uuid.UUID) -> Credencial | None:
    """RN-CRED-04: como maximo una credencial sin revocacion por participacion."""
    for credencial in credenciales_de(db, participacion_id):
        if credencial.esta_vigente():
            return credencial
    return None


def condicion_participacion(db: Session, participacion_id: uuid.UUID) -> CondicionParticipacion:
    """Propiedad derivada: nunca se persiste."""
    credenciales = credenciales_de(db, participacion_id)
    if not credenciales:
        return CondicionParticipacion.EN_PROGRESO
    if any(c.esta_vigente() for c in credenciales):
        return CondicionParticipacion.CERTIFICADA
    return CondicionParticipacion.REQUIERE_RECERTIFICACION


def momento_ultima_revocacion(db: Session, participacion_id: uuid.UUID):
    momentos = [
        c.revocacion.momento_revocacion for c in credenciales_de(db, participacion_id) if c.revocacion is not None
    ]
    return max(momentos) if momentos else None


def _contenido_emitido(credencial_datos: dict) -> tuple[str, str]:
    contenido = json.dumps(credencial_datos, ensure_ascii=False, sort_keys=True)
    return contenido, hashlib.sha256(contenido.encode()).hexdigest()


def emitir(db: Session, evaluacion: Evaluacion) -> Credencial:
    """Llamada interna del ServicioEvaluacion al aprobar. No se expone como accion del estudiante.

    PC-CERT-01: verificar la ausencia de otra credencial vigente y emitir forman una misma
    operacion coherente. La participacion se bloquea para que dos solicitudes simultaneas no
    produzcan dos credenciales vigentes.
    """
    # RN-CRED-03: solo una evaluacion finalizada y aprobada sustenta una credencial.
    if evaluacion.estado_procesamiento != EstadoEvaluacion.FINALIZADA:
        raise ErrorDominio("EVALUACION_NO_FINALIZADA", "La evaluacion no ha terminado.", http=409)
    if evaluacion.dictamen != Dictamen.APROBADO:
        raise ErrorDominio("EVALUACION_NO_APROBADA", "La evaluacion no obtuvo dictamen aprobado.", http=409)

    entrega = evaluacion.entrega
    # RN-CRED-01: la evaluacion sustentadora procede de una entrega de la misma participacion.
    #
    # `Participacion.reto` se carga con LEFT OUTER JOIN (lazy="joined"), y PostgreSQL rechaza
    # FOR UPDATE sobre el lado anulable de un outer join. Por eso la consulta de bloqueo no carga
    # relaciones (lazyload) y bloquea solo la fila de participacion (FOR UPDATE OF). Sin esto, en
    # produccion toda evaluacion APROBADA fallaba al emitir y quedaba en EN_EJECUCION sin
    # resultados: era el bloqueo que se vio en la demo del hackaton. SQLite no soporta FOR UPDATE,
    # por eso la suite local no lo detectaba; el job backend-postgres de CI la corre sobre PostgreSQL.
    consulta = select(Participacion).where(Participacion.id == entrega.participacion_id).options(lazyload("*"))
    if db.bind.dialect.name != "sqlite":
        consulta = consulta.with_for_update(of=Participacion)
    participacion = db.scalar(consulta)

    if (ya := credencial_vigente(db, participacion.id)) is not None:
        # RN-CRED-04: no se emite una segunda credencial vigente.
        raise ErrorDominio(
            "CREDENCIAL_VIGENTE_EXISTENTE",
            "La participacion ya conserva una credencial vigente.",
            http=409,
            detalles={"identificador_publico": ya.identificador_publico},
        )

    # RN-CRED-07: una evaluacion sustenta como maximo una credencial.
    if db.scalar(select(Credencial).where(Credencial.evaluacion_id == evaluacion.id)):
        raise ErrorDominio("EVALUACION_YA_CERTIFICADA", "Esa evaluacion ya sustenta una credencial.", http=409)

    # RN-CRED-06: recertificar exige una evaluacion iniciada despues de la ultima revocacion.
    ultima = momento_ultima_revocacion(db, participacion.id)
    if ultima is not None and (evaluacion.momento_inicio is None or evaluacion.momento_inicio <= ultima):
        raise ErrorDominio(
            "EVALUACION_ANTERIOR_A_LA_REVOCACION",
            "Recertificar exige una evaluacion iniciada despues de la ultima revocacion.",
            http=409,
        )

    reto = participacion.reto
    perfil = participacion.perfil
    momento = ahora()
    # RN-CRED-02: el emisor se deriva de la organizacion responsable del reto publicado.
    contenido, huella = _contenido_emitido(
        {
            "estudiante": perfil.nombre_publico,
            "reto": reto.titulo,
            "emisor": reto.organizacion.nombre,
            "criterios_aceptacion": reto.criterios_aceptacion,
            "commit": entrega.commit,
            "repositorio": entrega.repositorio,
            "version_evaluador": evaluacion.version_evaluador,
            "momento_emision": momento.isoformat(),
        }
    )

    credencial = Credencial(
        participacion_id=participacion.id,
        evaluacion_id=evaluacion.id,
        identificador_publico=_identificador_publico(momento.year),
        momento_emision=momento,
        contenido_emitido=contenido,
        huella_contenido=huella,
    )
    db.add(credencial)
    db.flush()

    auditoria.registrar(
        db,
        "credencial.emitida",
        auditoria.referencia("credencial", credencial.identificador_publico),
        origen=OrigenEvento.SISTEMA,
    )
    return credencial


def revocar(db: Session, credencial: Credencial, motivo: str, actor: Usuario) -> RevocacionCredencial:
    """RN-CRED-05: una credencial revocada permanece registrada y no vuelve a estar vigente."""
    if credencial.revocacion is not None:
        raise ErrorDominio("CREDENCIAL_YA_REVOCADA", "Esa credencial ya fue revocada.", http=409)

    revocacion = RevocacionCredencial(
        credencial_id=credencial.id, usuario_id=actor.id, motivo=motivo, momento_revocacion=ahora()
    )
    db.add(revocacion)
    db.flush()
    auditoria.registrar(
        db,
        "credencial.revocada",
        auditoria.referencia("credencial", credencial.identificador_publico),
        actor=actor,
        detalle=motivo,
    )
    return revocacion


def consultar(db: Session, identificador_publico: str) -> Credencial:
    credencial = db.scalar(select(Credencial).where(Credencial.identificador_publico == identificador_publico))
    if credencial is None:
        raise ErrorDominio("CREDENCIAL_NO_ENCONTRADA", "No existe esa credencial.", http=404)
    return credencial
