import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ErrorDominio
from app.dominio.enums import EstadoEvaluacion
from app.models import Credencial, Entrega, Evaluacion, ResultadoPrueba, RevisionIA, Usuario
from app.schemas.evaluacion import (
    CredencialResumen,
    EntregaEntrada,
    EntregaSalida,
    EvaluacionAceptada,
    EvaluacionSalida,
    ResultadoPruebaSalida,
)
from app.servicios import evaluacion as servicio_evaluacion
from app.servicios import juez_ia, seguridad

router = APIRouter()
settings = get_settings()
EN_PROCESO = (EstadoEvaluacion.PENDIENTE, EstadoEvaluacion.EN_EJECUCION)


@router.post(
    "/participaciones/{participacion_id}/entregas",
    response_model=EvaluacionAceptada,
    status_code=status.HTTP_202_ACCEPTED,
)
def registrar_entrega(
    participacion_id: uuid.UUID,
    datos: EntregaEntrada,
    tareas: BackgroundTasks,
    respuesta: Response,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(usuario_actual),
):
    """Registra la entrega y solicita su primera evaluacion. Responde 202.

    El actor se valida aqui; el procesamiento posterior corre con la identidad del servicio.
    """
    participacion = seguridad.participacion_propia(db, actor, participacion_id)
    entrega = servicio_evaluacion.registrar_entrega(db, participacion, datos.repositorio, datos.commit, actor)
    evaluacion = servicio_evaluacion.solicitar(db, entrega, actor)
    db.commit()
    db.refresh(evaluacion)

    tareas.add_task(servicio_evaluacion.procesar, evaluacion.id)
    ruta = f"{settings.API_V1_PREFIX}/evaluaciones/{evaluacion.id}"
    respuesta.headers["Location"] = ruta
    return EvaluacionAceptada(
        evaluacion_id=evaluacion.id,
        entrega_id=entrega.id,
        estado_procesamiento=evaluacion.estado_procesamiento,
        consultar_en=ruta,
    )


@router.post(
    "/entregas/{entrega_id}/evaluaciones", response_model=EvaluacionAceptada, status_code=status.HTTP_202_ACCEPTED
)
def reevaluar(
    entrega_id: uuid.UUID,
    tareas: BackgroundTasks,
    respuesta: Response,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(usuario_actual),
):
    """RN-EVAL-01: reevaluar no exige una entrega nueva.

    Es tambien la via de recertificacion (RN-CRED-06): una evaluacion iniciada despues de la
    ultima revocacion puede sustentar una credencial nueva sobre la misma entrega.
    """
    entrega = servicio_evaluacion.exigir_entrega_propia(db, actor, entrega_id)
    evaluacion = servicio_evaluacion.solicitar(db, entrega, actor)
    db.commit()
    db.refresh(evaluacion)

    tareas.add_task(servicio_evaluacion.procesar, evaluacion.id)
    ruta = f"{settings.API_V1_PREFIX}/evaluaciones/{evaluacion.id}"
    respuesta.headers["Location"] = ruta
    return EvaluacionAceptada(
        evaluacion_id=evaluacion.id,
        entrega_id=entrega.id,
        estado_procesamiento=evaluacion.estado_procesamiento,
        consultar_en=ruta,
    )


@router.get("/participaciones/{participacion_id}/entregas", response_model=list[EntregaSalida])
def historial(participacion_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    participacion = seguridad.participacion_propia(db, actor, participacion_id)
    filas = db.scalars(
        select(Entrega).where(Entrega.participacion_id == participacion.id).order_by(Entrega.numero_intento.desc())
    ).all()
    return [
        EntregaSalida(
            id=e.id,
            participacion_id=e.participacion_id,
            numero_intento=e.numero_intento,
            momento_entrega=e.momento_entrega,
            repositorio=e.repositorio,
            commit=e.commit,
            huella_proyecto=e.huella_proyecto,
            evaluaciones=[ev.id for ev in e.evaluaciones],
        )
        for e in filas
    ]


@router.get("/evaluaciones/{evaluacion_id}", response_model=EvaluacionSalida)
def estado_evaluacion(
    evaluacion_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)
):
    """La consulta que alimenta la pantalla de evaluacion en vivo."""
    evaluacion = db.get(Evaluacion, evaluacion_id)
    if evaluacion is None:
        raise ErrorDominio("EVALUACION_NO_ENCONTRADA", "No existe esa evaluacion.", http=404)
    seguridad.participacion_propia(db, actor, evaluacion.entrega.participacion_id)
    if evaluacion.estado_procesamiento in EN_PROCESO and servicio_evaluacion.cerrar_colgadas(db):
        db.refresh(evaluacion)

    salida = EvaluacionSalida(
        id=evaluacion.id,
        entrega_id=evaluacion.entrega_id,
        estado_procesamiento=evaluacion.estado_procesamiento,
        momento_solicitud=evaluacion.momento_solicitud,
        momento_inicio=evaluacion.momento_inicio,
        momento_fin=evaluacion.momento_fin,
        version_evaluador=evaluacion.version_evaluador,
        dictamen=evaluacion.dictamen,
        detalle_error=evaluacion.detalle_error,
    )

    total_pruebas = len(evaluacion.entrega.participacion.reto.pruebas)
    if evaluacion.estado_procesamiento in EN_PROCESO:
        # El progreso sale de filas realmente persistidas, no de una estimacion.
        hechos = (
            db.scalar(
                select(func.count()).select_from(ResultadoPrueba).where(ResultadoPrueba.evaluacion_id == evaluacion.id)
            )
            or 0
        )
        salida.progreso = {"pruebas_totales": total_pruebas, "pruebas_ejecutadas": hechos}
        return salida

    salida.resultados = [
        ResultadoPruebaSalida(
            prueba_id=r.prueba_id,
            prueba=r.prueba.nombre,
            categoria=r.prueba.categoria,
            obligatoria=r.prueba.obligatoria,
            condicion_ejecucion=r.condicion_ejecucion,
            aprobada=r.aprobada,
            valor_observado=float(r.valor_observado) if r.valor_observado is not None else None,
            unidad=r.unidad,
            duracion_ms=r.duracion_ms,
            detalle=r.detalle,
        )
        for r in evaluacion.resultados
    ]

    salida.revision_ia = juez_ia.a_dict(db.get(RevisionIA, evaluacion.id))

    credencial = db.scalar(select(Credencial).where(Credencial.evaluacion_id == evaluacion.id))
    if credencial:
        salida.credencial = CredencialResumen(
            identificador_publico=credencial.identificador_publico,
            vigente=credencial.esta_vigente(),
            url_verificacion=f"{settings.URL_BASE_VERIFICACION}/{credencial.identificador_publico}",
        )
    return salida
