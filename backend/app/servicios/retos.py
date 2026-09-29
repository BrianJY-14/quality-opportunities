"""ServicioRetos del UML.

Prepara el borrador con IA, aplica autorizacion y publica solo tras revision.
"""

import json
import uuid

from sqlalchemy.orm import Session

from app.core.errors import ErrorDominio
from app.dominio.enums import EstadoPreparacion, EstadoReto, OrigenEvento, ResultadoOperacion
from app.models import Prueba, Reto, SolicitudReto, Usuario
from app.models._base import ahora
from app.servicios import auditoria, seguridad
from app.servicios.registro import obtener_preparador
from app.servicios.workspace import documento_canonico


def registrar_solicitud(
    db: Session, actor: Usuario, organizacion_id: uuid.UUID, titulo: str, contenido: str
) -> SolicitudReto:
    seguridad.exigir_gestion_de_retos(
        db, actor, organizacion_id, "solicitud.registrada", auditoria.referencia("organizacion", organizacion_id)
    )

    solicitud = SolicitudReto(
        representante_usuario_id=actor.id,
        organizacion_id=organizacion_id,
        titulo_original=titulo,
        contenido_original_restringido=contenido,
        estado_preparacion=EstadoPreparacion.RECIBIDA,
    )
    db.add(solicitud)
    db.flush()
    auditoria.registrar(db, "solicitud.registrada", auditoria.referencia("solicitud", solicitud.id), actor=actor)
    return solicitud


def preparar(db: Session, solicitud_id: uuid.UUID) -> Reto:
    """Trabajo en segundo plano. RN-ING-02: la salida es un BORRADOR; publicar exige revision.

    RN-ING-01: si el reto proviene de una solicitud, su responsable coincide con la
    organizacion de la representacion que la presento.
    """
    with_session = db
    solicitud = with_session.get(SolicitudReto, solicitud_id)
    if solicitud is None or solicitud.estado_preparacion not in (EstadoPreparacion.RECIBIDA, EstadoPreparacion.ERROR):
        return None

    solicitud.estado_preparacion = EstadoPreparacion.PROCESANDO
    with_session.flush()

    try:
        borrador = obtener_preparador().proponer(
            solicitud.titulo_original, solicitud.contenido_original_restringido or ""
        )
    except Exception as error:  # noqa: BLE001 -- cualquier fallo del preparador deja rastro
        solicitud.estado_preparacion = EstadoPreparacion.ERROR
        solicitud.detalle_error = "El preparador no pudo proponer un borrador."
        auditoria.registrar(
            with_session,
            "solicitud.preparacion_fallida",
            auditoria.referencia("solicitud", solicitud.id),
            ResultadoOperacion.ERROR,
            origen=OrigenEvento.SISTEMA,
            detalle=type(error).__name__,
        )
        with_session.commit()
        return None

    solicitud.estado_preparacion = EstadoPreparacion.LISTA
    solicitud.modelo_ia = borrador.modelo
    solicitud.version_instrucciones = borrador.version_instrucciones
    solicitud.resumen_preparacion = borrador.resumen_preparacion

    reto = Reto(
        organizacion_id=solicitud.organizacion_id,
        solicitud_id=solicitud.id,
        titulo=borrador.titulo,
        descripcion_publica=borrador.descripcion_publica,
        criterios_aceptacion=borrador.criterios_aceptacion,
        repositorio_base=borrador.repositorio_base,
        version_base=borrador.version_base,
        estado=EstadoReto.BORRADOR,
        dificultad=borrador.dificultad,
        aptitudes=json.dumps(borrador.aptitudes, ensure_ascii=False) if borrador.aptitudes else None,
        proyecto_base=documento_canonico(borrador.proyecto_base) if borrador.proyecto_base else None,
    )
    with_session.add(reto)
    with_session.flush()

    for propuesta in borrador.pruebas:
        with_session.add(
            Prueba(
                reto_id=reto.id,
                nombre=propuesta.nombre,
                categoria=propuesta.categoria,
                obligatoria=propuesta.obligatoria,
                condicion_aprobacion=propuesta.condicion_aprobacion,
                referencia_ejecutable=propuesta.referencia_ejecutable,
                limite_ejecucion_ms=propuesta.limite_ejecucion_ms,
                contenido_ejecutable=propuesta.contenido_ejecutable,
            )
        )

    auditoria.registrar(
        with_session,
        "reto.borrador_preparado",
        auditoria.referencia("reto", reto.id),
        origen=OrigenEvento.SISTEMA,
        detalle=f"modelo={borrador.modelo}",
    )
    with_session.commit()
    return reto


def publicar(db: Session, reto: Reto, actor: Usuario) -> Reto:
    """RN-ING-02: revision humana autorizada del texto final y de las condiciones de evaluacion.

    Publicar exige al menos una prueba obligatoria (seccion 3 del diseno)."""
    seguridad.exigir_gestion_de_retos(
        db, actor, reto.organizacion_id, "reto.publicado", auditoria.referencia("reto", reto.id)
    )

    if reto.estado != EstadoReto.BORRADOR:
        raise ErrorDominio(
            "RETO_NO_ES_BORRADOR",
            "Solo un reto en borrador puede publicarse.",
            http=409,
            detalles={"estado": reto.estado},
        )
    if not any(p.obligatoria for p in reto.pruebas):
        raise ErrorDominio("SIN_PRUEBA_OBLIGATORIA", "Publicar exige al menos una prueba obligatoria.", http=409)

    reto.estado = EstadoReto.PUBLICADO
    reto.momento_publicacion = ahora()
    auditoria.registrar(db, "reto.publicado", auditoria.referencia("reto", reto.id), actor=actor)
    db.commit()
    return reto


def cerrar(db: Session, reto: Reto, actor: Usuario) -> Reto:
    """RN-RETO-01: cerrar cambia la disponibilidad, no la evidencia historica."""
    seguridad.exigir_gestion_de_retos(
        db, actor, reto.organizacion_id, "reto.cerrado", auditoria.referencia("reto", reto.id)
    )

    if reto.estado != EstadoReto.PUBLICADO:
        raise ErrorDominio("RETO_NO_PUBLICADO", "Solo un reto publicado puede cerrarse.", http=409)

    reto.estado = EstadoReto.CERRADO
    reto.momento_cierre = ahora()
    auditoria.registrar(db, "reto.cerrado", auditoria.referencia("reto", reto.id), actor=actor)
    db.commit()
    return reto
