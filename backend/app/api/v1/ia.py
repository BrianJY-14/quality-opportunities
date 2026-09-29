"""Rutas de las funciones de IA: tutor, juez, defensa tecnica, CV dinamico y ranking."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ErrorDominio
from app.dominio import rangos
from app.dominio.enums import VisibilidadPerfil
from app.models import Defensa, EspacioTrabajo, Evaluacion, PerfilEstudiante, RevisionIA, Usuario
from app.servicios import auditoria, cv, defensa_ia, juez_ia, llm, seguridad, tutor_ia
from app.servicios import evaluacion as servicio_evaluacion
from app.servicios import workspace as servicio_workspace

router = APIRouter()
settings = get_settings()


# ------------------------------------------------------------------ estado


@router.get("/ia/estado", tags=["ia"])
def estado_ia():
    """Declara si hay un modelo configurado y cual. Transparencia deliberada, como /meta."""
    cliente = llm.obtener_cliente()
    return {
        "llm_configurado": cliente.disponible,
        "modelo": cliente.etiqueta if cliente.disponible else None,
        "preparador": settings.PREPARADOR,
        "funciones": {
            "ai_scoper": "llm" if settings.PREPARADOR == "llm" and cliente.disponible else "reglas",
            "juez_ia": "llm" if cliente.disponible else "estatico",
            "tutor_ia": "llm" if cliente.disponible else "reglas",
            "defensa_ia": "llm" if cliente.disponible else "plantilla_sin_calificacion",
            "resumen_cv": "llm" if cliente.disponible else "no_disponible",
        },
    }


# ------------------------------------------------------------------ tutor


class ConsultaTutor(BaseModel):
    pregunta: str | None = Field(default=None, max_length=600)


@router.post("/participaciones/{participacion_id}/tutor", tags=["ia"])
def consultar_tutor(
    participacion_id: uuid.UUID,
    datos: ConsultaTutor,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(usuario_actual),
):
    """Diagnosticos y pistas sobre la revision GUARDADA. No crea entrega ni evaluacion."""
    participacion = seguridad.participacion_propia(db, actor, participacion_id)
    espacio = db.get(EspacioTrabajo, participacion.id)
    archivos = servicio_workspace.leer_archivos(espacio.archivos) if espacio else []
    return tutor_ia.consultar(
        str(actor.id), participacion.reto, archivos, espacio.revision if espacio else 0, datos.pregunta
    )


# ------------------------------------------------------------------ juez


@router.get("/evaluaciones/{evaluacion_id}/revision-ia", tags=["ia"])
def revision_ia(evaluacion_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    evaluacion = db.get(Evaluacion, evaluacion_id)
    if evaluacion is None:
        raise ErrorDominio("EVALUACION_NO_ENCONTRADA", "No existe esa evaluacion.", http=404)
    seguridad.participacion_propia(db, actor, evaluacion.entrega.participacion_id)
    revision = db.get(RevisionIA, evaluacion.id)
    if revision is None:
        raise ErrorDominio("REVISION_NO_DISPONIBLE", "La revision del Juez IA aun no existe.", http=404)
    return juez_ia.a_dict(revision)


@router.post("/evaluaciones/{evaluacion_id}/revision-ia", tags=["ia"])
def reintentar_revision_ia(
    evaluacion_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)
):
    """Vuelve a pedir la revision al modelo cuando quedo solo con metricas estaticas.

    No cambia el dictamen ni crea una evaluacion nueva. Una revision ya hecha por el modelo se
    devuelve tal cual.
    """
    evaluacion = db.get(Evaluacion, evaluacion_id)
    if evaluacion is None:
        raise ErrorDominio("EVALUACION_NO_ENCONTRADA", "No existe esa evaluacion.", http=404)
    seguridad.participacion_propia(db, actor, evaluacion.entrega.participacion_id)
    if evaluacion.dictamen is None:
        raise ErrorDominio("EVALUACION_SIN_DICTAMEN", "La evaluacion aun no termina o cerro sin dictamen.", http=409)
    revision = juez_ia.revisar(db, evaluacion, reintentar=True)
    db.commit()
    return juez_ia.a_dict(revision)


# ------------------------------------------------------------------ defensa


class Respuesta(BaseModel):
    pregunta_id: str = Field(min_length=1, max_length=10)
    respuesta: str = Field(min_length=20, max_length=1500)


class RespuestasDefensa(BaseModel):
    respuestas: list[Respuesta] = Field(min_length=1, max_length=5)


@router.post("/entregas/{entrega_id}/defensas", status_code=status.HTTP_201_CREATED, tags=["ia"])
def iniciar_defensa(entrega_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    """Genera las preguntas sobre el codigo de la entrega. Repetir devuelve la defensa pendiente."""
    entrega = servicio_evaluacion.exigir_entrega_propia(db, actor, entrega_id)
    defensa = defensa_ia.generar(db, entrega)
    auditoria.registrar(db, "defensa.iniciada", auditoria.referencia("defensa", defensa.id), actor=actor)
    db.commit()
    return defensa_ia.a_dict(defensa)


@router.get("/entregas/{entrega_id}/defensas", tags=["ia"])
def defensas_de_entrega(entrega_id: uuid.UUID, db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    entrega = servicio_evaluacion.exigir_entrega_propia(db, actor, entrega_id)
    filas = db.scalars(
        select(Defensa).where(Defensa.entrega_id == entrega.id).order_by(Defensa.momento_creacion.desc())
    ).all()
    return [defensa_ia.a_dict(d) for d in filas]


@router.post("/defensas/{defensa_id}/respuestas", tags=["ia"])
def responder_defensa(
    defensa_id: uuid.UUID,
    datos: RespuestasDefensa,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(usuario_actual),
):
    defensa = db.get(Defensa, defensa_id)
    if defensa is None:
        raise ErrorDominio("DEFENSA_NO_ENCONTRADA", "No existe esa defensa.", http=404)
    seguridad.participacion_propia(db, actor, defensa.entrega.participacion_id)
    defensa_ia.responder(db, defensa, [r.model_dump() for r in datos.respuestas])
    auditoria.registrar(
        db,
        "defensa.respondida",
        auditoria.referencia("defensa", defensa.id),
        actor=actor,
        detalle=f"estado={defensa.estado} puntaje={defensa.puntaje}",
    )
    db.commit()
    return defensa_ia.a_dict(defensa)


# ------------------------------------------------------------------ CV y ranking


@router.get("/perfiles/{nombre_publico}/cv", tags=["cv"])
def cv_publico(nombre_publico: str, db: Session = Depends(get_db)):
    """CV dinamico publico. Un perfil privado devuelve 404: no se confirma su existencia."""
    perfil = db.scalar(select(PerfilEstudiante).where(PerfilEstudiante.nombre_publico == nombre_publico))
    if perfil is None or perfil.visibilidad != VisibilidadPerfil.PUBLICO:
        raise ErrorDominio("PERFIL_NO_ENCONTRADO", "No existe ese perfil publico.", http=404)
    return cv.construir(db, perfil)


@router.get("/auth/yo/cv", tags=["cv"])
def mi_cv(db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    return cv.construir(db, seguridad.perfil_propio(db, actor))


@router.post("/auth/yo/cv/resumen", tags=["cv"])
def generar_resumen(db: Session = Depends(get_db), actor: Usuario = Depends(usuario_actual)):
    """El LLM redacta el resumen profesional a partir SOLO de la evidencia verificada."""
    perfil = seguridad.perfil_propio(db, actor)
    cv.generar_resumen(db, perfil)
    auditoria.registrar(db, "cv.resumen_generado", f"perfil:{perfil.usuario_id}", actor=actor)
    db.commit()
    return {"resumen_ia": perfil.resumen_ia, "momento_resumen": perfil.momento_resumen}


@router.get("/ranking", tags=["cv"])
def ranking(limite: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    return {"rangos": rangos.tabla(), "filas": cv.ranking(db, limite)}
