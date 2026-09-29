import json
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.core.database import get_db
from app.core.errors import ErrorDominio
from app.dominio.enums import EstadoReto
from app.models import Reto, Usuario
from app.schemas.comunes import Pagina
from app.schemas.reto import (
    OrganizacionSalida,
    PruebaBorrador,
    PruebaSalida,
    RetoActualizar,
    RetoBorrador,
    RetoDetalle,
    RetoResumen,
)
from app.servicios import retos as servicio_retos
from app.servicios import seguridad
from app.servicios.workspace import leer_archivos

router = APIRouter()


def _resumen(reto: Reto) -> dict:
    return {
        "id": reto.id,
        "titulo": reto.titulo,
        "estado": reto.estado,
        "organizacion": OrganizacionSalida(
            id=reto.organizacion.id,
            nombre=reto.organizacion.nombre,
            logo=reto.organizacion.logo,
            sitio_web=reto.organizacion.sitio_web,
        ),
        "momento_publicacion": reto.momento_publicacion,
        "momento_cierre": reto.momento_cierre,
        "pruebas_obligatorias": sum(1 for p in reto.pruebas if p.obligatoria),
        "pruebas_totales": len(reto.pruebas),
        "dificultad": reto.dificultad,
        "aptitudes": _aptitudes(reto),
    }


def _aptitudes(reto: Reto) -> list[str]:
    try:
        valor = json.loads(reto.aptitudes or "[]")
        return [str(a) for a in valor] if isinstance(valor, list) else []
    except json.JSONDecodeError:
        return []


def _prueba(p) -> PruebaSalida:
    salida = PruebaSalida.model_validate(p, from_attributes=True)
    salida.tiene_codigo = bool(p.contenido_ejecutable)
    return salida


@router.get("/retos", response_model=Pagina[RetoResumen])
def listar(
    db: Session = Depends(get_db),
    estado: EstadoReto = EstadoReto.PUBLICADO,
    organizacion_id: uuid.UUID | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    """Catalogo publico. Los borradores no se listan aqui: se consultan desde el portal."""
    consulta = select(Reto).where(Reto.estado == estado)
    if estado == EstadoReto.BORRADOR:
        raise ErrorDominio(
            "ESTADO_NO_PUBLICO", "Los borradores se consultan desde el portal de la organizacion.", http=403
        )
    if organizacion_id:
        consulta = consulta.where(Reto.organizacion_id == organizacion_id)
    if q:
        consulta = consulta.where(Reto.titulo.ilike(f"%{q}%"))

    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    # Lo recien publicado primero; el titulo desempata para que la paginacion sea estable.
    consulta = consulta.order_by(Reto.momento_publicacion.desc(), Reto.titulo)
    filas = db.scalars(consulta.offset((page - 1) * size).limit(size)).unique().all()
    return Pagina[RetoResumen](items=[RetoResumen(**_resumen(r)) for r in filas], total=total, page=page, size=size)


def reto_visible(db: Session, reto_id: uuid.UUID) -> Reto:
    reto = db.get(Reto, reto_id)
    if reto is None:
        raise ErrorDominio("RETO_NO_ENCONTRADO", "No existe ese reto.", http=404)
    return reto


@router.get("/retos/{reto_id}", response_model=RetoDetalle)
def detalle(reto_id: uuid.UUID, db: Session = Depends(get_db)):
    reto = reto_visible(db, reto_id)
    if reto.estado == EstadoReto.BORRADOR:
        raise ErrorDominio("RETO_NO_ENCONTRADO", "No existe ese reto.", http=404)
    return _detalle(reto)


def _detalle(reto: Reto) -> RetoDetalle:
    return RetoDetalle(
        **_resumen(reto),
        descripcion_publica=reto.descripcion_publica,
        criterios_aceptacion=reto.criterios_aceptacion,
        repositorio_base=reto.repositorio_base,
        version_base=reto.version_base,
        pruebas=[_prueba(p) for p in reto.pruebas],
    )


def _borrador(reto: Reto) -> RetoBorrador:
    base = _detalle(reto).model_dump(exclude={"pruebas"})
    return RetoBorrador(
        **base,
        pruebas=[
            PruebaBorrador(
                **_prueba(p).model_dump(),
                referencia_ejecutable=p.referencia_ejecutable,
                contenido_ejecutable=p.contenido_ejecutable,
            )
            for p in reto.pruebas
        ],
        proyecto_base=leer_archivos(reto.proyecto_base) if reto.proyecto_base else [],
    )


@router.get("/organizaciones/{organizacion_id}/retos", response_model=list[RetoResumen])
def retos_de_organizacion(
    organizacion_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)
):
    """Portal de la organizacion: todos sus retos, incluidos los borradores que prepara la IA."""
    seguridad.exigir_gestion_de_retos(
        db, actor, organizacion_id, "organizacion.retos_consultados", f"organizacion:{organizacion_id}"
    )
    filas = db.scalars(select(Reto).where(Reto.organizacion_id == organizacion_id)).unique().all()
    orden = {EstadoReto.BORRADOR: 0, EstadoReto.PUBLICADO: 1, EstadoReto.CERRADO: 2}
    filas = sorted(filas, key=lambda r: (orden.get(r.estado, 3), r.titulo))
    return [RetoResumen(**_resumen(r)) for r in filas]


@router.get("/retos/{reto_id}/borrador", response_model=RetoBorrador)
def ver_borrador(reto_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    """RN-ING-02: el representante revisa el borrador antes de publicar."""
    reto = reto_visible(db, reto_id)
    seguridad.exigir_gestion_de_retos(db, actor, reto.organizacion_id, "reto.borrador_consultado", f"reto:{reto.id}")
    return _borrador(reto)


@router.patch("/retos/{reto_id}", response_model=RetoBorrador)
def corregir_borrador(
    reto_id: uuid.UUID, datos: RetoActualizar, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)
):
    """La revision humana puede corregir el texto propuesto por la IA antes de publicar."""
    reto = reto_visible(db, reto_id)
    seguridad.exigir_gestion_de_retos(db, actor, reto.organizacion_id, "reto.corregido", f"reto:{reto.id}")
    if reto.estado != EstadoReto.BORRADOR:
        raise ErrorDominio("RETO_NO_ES_BORRADOR", "Tras publicar se fijan criterios y pruebas certificables.", http=409)
    for campo, valor in datos.model_dump(exclude_none=True).items():
        if campo == "aptitudes":
            valor = json.dumps([a.strip() for a in valor if a.strip()][:8], ensure_ascii=False)
        setattr(reto, campo, valor)
    db.commit()
    db.refresh(reto)
    return _borrador(reto)


@router.post("/retos/{reto_id}/publicacion", response_model=RetoDetalle)
def publicar(reto_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    return _detalle(servicio_retos.publicar(db, reto_visible(db, reto_id), actor))


@router.post("/retos/{reto_id}/cierre", response_model=RetoDetalle)
def cerrar(reto_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    return _detalle(servicio_retos.cerrar(db, reto_visible(db, reto_id), actor))
