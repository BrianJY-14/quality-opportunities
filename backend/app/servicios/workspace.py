"""Servicio del espacio de trabajo del editor web.

Guardar un borrador NO crea una entrega ni incrementa el numero de intento. Es la regla 3 del
procedimiento y la razon por la que esta tabla existe aparte de `Entrega`.

Aqui vive tambien la forma canonica del proyecto, que se reutiliza al congelar una entrega: si el
documento se serializara de dos maneras distintas, la huella del borrador y la de la entrega no
coincidirian y la verificacion posterior seria inutil.
"""

import hashlib
import json

from sqlalchemy.orm import Session

from app.core.errors import ErrorDominio
from app.models import EspacioTrabajo, Participacion
from app.models._base import ahora
from app.models.workspace import PROYECTO_VACIO

VERSION_FORMATO = 1


def documento_canonico(archivos: list[dict]) -> str:
    """Serializacion unica y reproducible del proyecto.

    Orden por ruta ASCII, claves ordenadas, sin espacios accesorios y sin escapes innecesarios:
    los mismos archivos producen siempre los mismos bytes, y por tanto la misma huella.
    """
    ordenados = sorted(
        ({"ruta": a["ruta"], "contenido": a["contenido"]} for a in archivos),
        key=lambda a: a["ruta"],
    )
    return json.dumps(
        {"version": VERSION_FORMATO, "archivos": ordenados},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def huella(documento: str) -> str:
    """SHA-256 sobre los bytes exactos del documento canonico."""
    return hashlib.sha256(documento.encode("utf-8")).hexdigest()


def leer_archivos(documento: str) -> list[dict]:
    try:
        datos = json.loads(documento)
        return list(datos.get("archivos", []))
    except (json.JSONDecodeError, AttributeError):
        return []


def obtener_o_crear(db: Session, participacion: Participacion) -> EspacioTrabajo:
    """Abrir el espacio no borra lo que ya habia.

    La primera vez se inicializa con el proyecto base del reto (U1, paso 3) si lo tiene; si no,
    nace vacio y el editor muestra un proyecto en blanco. Solo ocurre una vez: volver a abrir
    nunca reemplaza el trabajo del estudiante por el proyecto base."""
    espacio = db.get(EspacioTrabajo, participacion.id)
    if espacio is not None:
        return espacio

    base = participacion.reto.proyecto_base if participacion.reto else None
    documento = documento_canonico(leer_archivos(base)) if base and leer_archivos(base) else PROYECTO_VACIO
    espacio = EspacioTrabajo(
        participacion_id=participacion.id,
        revision=0,
        archivos=documento,
        bytes_total=len(documento.encode("utf-8")) if documento != PROYECTO_VACIO else 0,
    )
    db.add(espacio)
    db.flush()
    return espacio


def guardar(db: Session, espacio: EspacioTrabajo, revision_base: int, archivos: list[dict]) -> EspacioTrabajo:
    """Concurrencia optimista: solo escribe quien parte de la revision vigente.

    Sin esta comprobacion, dos pestanas abiertas del editor se sobrescriben en silencio y el
    estudiante pierde trabajo sin enterarse.
    """
    if revision_base != espacio.revision:
        raise ErrorDominio(
            "BORRADOR_DESACTUALIZADO",
            "Existe una revision mas reciente. Recarga antes de guardar.",
            http=409,
            detalles={"revision_actual": espacio.revision, "revision_enviada": revision_base},
        )

    documento = documento_canonico(archivos)
    espacio.archivos = documento
    espacio.bytes_total = len(documento.encode("utf-8"))
    espacio.revision = espacio.revision + 1
    espacio.momento_guardado = ahora()
    db.flush()
    return espacio
