import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.core.database import SessionLocal, get_db
from app.core.errors import ErrorDominio
from app.models import Reto, SolicitudReto, Usuario
from app.schemas.reto import SolicitudEntrada, SolicitudSalida
from app.servicios import retos as servicio_retos
from app.servicios import seguridad

router = APIRouter()


def _preparar_en_segundo_plano(solicitud_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        servicio_retos.preparar(db, solicitud_id)


def _salida(db: Session, solicitud: SolicitudReto) -> SolicitudSalida:
    borrador = db.scalar(select(Reto).where(Reto.solicitud_id == solicitud.id))
    return SolicitudSalida(
        id=solicitud.id,
        titulo_original=solicitud.titulo_original,
        estado_preparacion=solicitud.estado_preparacion,
        momento_recepcion=solicitud.momento_recepcion,
        modelo_ia=solicitud.modelo_ia,
        version_instrucciones=solicitud.version_instrucciones,
        resumen_preparacion=solicitud.resumen_preparacion,
        detalle_error=solicitud.detalle_error,
        reto_borrador_id=borrador.id if borrador else None,
    )


@router.post("/solicitudes", response_model=SolicitudSalida, status_code=status.HTTP_202_ACCEPTED)
def registrar(
    datos: SolicitudEntrada,
    tareas: BackgroundTasks,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(usuario_actual),
):
    """La preparacion con IA corre fuera del ciclo de peticion y produce un BORRADOR."""
    solicitud = servicio_retos.registrar_solicitud(
        db, actor, datos.organizacion_id, datos.titulo_original, datos.contenido_original
    )
    db.commit()
    db.refresh(solicitud)
    tareas.add_task(_preparar_en_segundo_plano, solicitud.id)
    return _salida(db, solicitud)


@router.get("/solicitudes/{solicitud_id}", response_model=SolicitudSalida)
def consultar(solicitud_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    solicitud = db.get(SolicitudReto, solicitud_id)
    if solicitud is None:
        raise ErrorDominio("SOLICITUD_NO_ENCONTRADA", "No existe esa solicitud.", http=404)
    seguridad.exigir_gestion_de_retos(
        db, actor, solicitud.organizacion_id, "solicitud.consultada", f"solicitud:{solicitud.id}"
    )
    return _salida(db, solicitud)


@router.get("/organizaciones/{organizacion_id}/solicitudes", response_model=list[SolicitudSalida])
def listar(organizacion_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    """Historial de issues enviados por la organizacion al AI Scoper, del mas reciente al mas antiguo."""
    seguridad.exigir_gestion_de_retos(
        db, actor, organizacion_id, "solicitud.listada", f"organizacion:{organizacion_id}"
    )
    filas = db.scalars(
        select(SolicitudReto)
        .where(SolicitudReto.organizacion_id == organizacion_id)
        .order_by(SolicitudReto.momento_recepcion.desc())
        .limit(50)
    ).all()
    return [_salida(db, s) for s in filas]
