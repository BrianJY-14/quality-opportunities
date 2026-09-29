"""Defensa tecnica con IA: entrevista sobre el codigo que el estudiante entrego.

Responde a una debilidad que el proyecto documenta: una prueba automatica demuestra que el codigo
funciona, no que quien lo entrega lo entiende (el 95% de las tareas se pueden resolver con IA sin
supervision). La defensa pregunta por decisiones concretas de ESE codigo:

1. `generar`: el modelo lee la copia congelada de la entrega y formula 3 preguntas sobre sus
   decisiones, con una rubrica privada de puntos clave que el estudiante no ve.
2. `responder`: el modelo califica cada respuesta de 0 a 100 contra la rubrica y el codigo, y
   penaliza respuestas genericas que no citan la implementacion. Aprueba con 60 o mas.

Diferencia deliberada con la version 1 del procedimiento: alli la defensa era de opcion multiple
con correccion simulada porque no habia un evaluador de texto real. Con un modelo invocado de
verdad se puede calificar la respuesta abierta, y el informe dice que modelo lo hizo.

La defensa no bloquea la evaluacion oficial: suma al CV y al ranking. Sin modelo, las preguntas
salen de plantillas sobre las funciones detectadas y las respuestas quedan SIN_CALIFICAR.
"""

import json
import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ErrorDominio
from app.models import Defensa, Entrega
from app.models._base import ahora
from app.servicios import llm
from app.servicios import workspace as servicio_workspace

log = logging.getLogger("defensa_ia")

MAX_DEFENSAS_POR_ENTREGA = 3
UMBRAL_APROBACION = 60

INSTRUCCIONES_PREGUNTAS = """Eres el entrevistador tecnico de Quality Opportunities. Un estudiante entrego esta solucion a un
reto. Formula exactamente 3 preguntas para comprobar que ENTIENDE su propio codigo:
- una sobre una decision de diseno concreta (por que asi y no de otra forma),
- una sobre un caso limite o fallo (que pasa si...),
- una sobre un cambio de condiciones (como adaptarias X si la carga o el requisito cambia).

Cada pregunta debe citar una funcion, archivo o linea real del codigo. No preguntes definiciones de libro.

Devuelve UNICAMENTE este JSON:
{"preguntas": [{"id": "p1", "pregunta": "texto", "enfoque": "DISENO | CASO_LIMITE | ADAPTACION", "archivo": "main.py", "puntos_clave": ["2 a 4 ideas que una buena respuesta deberia mencionar"]}]}
En espanol, sin emojis."""

INSTRUCCIONES_CALIFICACION = """Eres el evaluador de la defensa tecnica de Quality Opportunities. Califica cada respuesta del
estudiante de 0 a 100 comparandola con los puntos clave de la rubrica y con el codigo real.

Criterios: correccion tecnica (50%), referencia concreta a su implementacion (30%), claridad (20%).
Una respuesta generica que podria servir para cualquier codigo no supera 40. Una respuesta que
contradice lo que el codigo hace no supera 30. No premies la longitud.

Devuelve UNICAMENTE este JSON:
{"calificaciones": [{"id": "p1", "puntaje": 0, "comentario": "que estuvo bien y que falto, 1-2 frases"}],
 "retroalimentacion": "2-3 frases impersonales con los temas a reforzar"}
En espanol, sin emojis."""


def _archivos(db: Session, entrega: Entrega) -> list[dict]:
    if entrega.proyecto:
        return servicio_workspace.leer_archivos(entrega.proyecto)
    from app.models import EspacioTrabajo

    espacio = db.get(EspacioTrabajo, entrega.participacion_id)
    return servicio_workspace.leer_archivos(espacio.archivos) if espacio else []


def _preguntas_plantilla(archivos: list[dict]) -> list[dict]:
    """Respaldo sin modelo: preguntas sobre las funciones que existen en el proyecto."""
    import ast

    funciones = []
    for a in archivos:
        if not a.get("ruta", "").endswith(".py"):
            continue
        try:
            arbol = ast.parse(a.get("contenido", ""))
        except SyntaxError:
            continue
        funciones += [
            (a["ruta"], n.name)
            for n in ast.walk(arbol)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and not n.name.startswith("test_")
        ]
    ruta, nombre = funciones[0] if funciones else ("main.py", "la funcion principal")
    return [
        {
            "id": "p1",
            "pregunta": f"Explica la responsabilidad de '{nombre}' en {ruta} y por que se organizo asi.",
            "enfoque": "DISENO",
            "archivo": ruta,
        },
        {
            "id": "p2",
            "pregunta": f"Que ocurre en '{nombre}' si recibe una entrada vacia o invalida? Cita la linea que lo maneja.",
            "enfoque": "CASO_LIMITE",
            "archivo": ruta,
        },
        {
            "id": "p3",
            "pregunta": "Si el volumen de datos se multiplicara por 100, que parte de la solucion cambiarias primero y por que?",
            "enfoque": "ADAPTACION",
            "archivo": ruta,
        },
    ]


def generar(db: Session, entrega: Entrega, cliente=None) -> Defensa:
    pendiente = db.scalar(select(Defensa).where(Defensa.entrega_id == entrega.id, Defensa.estado == "PENDIENTE"))
    if pendiente is not None:
        return pendiente

    hechas = db.scalar(select(func.count()).select_from(Defensa).where(Defensa.entrega_id == entrega.id)) or 0
    if hechas >= MAX_DEFENSAS_POR_ENTREGA:
        raise ErrorDominio(
            "DEFENSAS_AGOTADAS",
            f"Esta entrega ya tuvo {MAX_DEFENSAS_POR_ENTREGA} defensas. Envia una nueva entrega para defender otra vez.",
            http=409,
        )

    archivos = _archivos(db, entrega)
    if not any(a.get("ruta", "").endswith(".py") for a in archivos):
        raise ErrorDominio(
            "ENTREGA_SIN_CODIGO", "La entrega no tiene archivos Python del editor sobre los que preguntar.", http=409
        )

    cliente = cliente or llm.obtener_cliente()
    preguntas, rubrica, modelo = None, [], "plantilla:v1"
    if cliente.disponible:
        reto = entrega.participacion.reto
        try:
            datos = cliente.json(
                INSTRUCCIONES_PREGUNTAS + llm.AVISO_CODIGO,
                f"Reto: {reto.titulo}\n{reto.descripcion_publica[:1200]}\n\nCodigo entregado:\n"
                f"{llm.codigo_para_prompt(archivos, 16000)}",
                max_tokens=1200,
                temperatura=0.5,
            )
            crudas = [p for p in (datos.get("preguntas") or []) if isinstance(p, dict) and p.get("pregunta")][:3]
            if len(crudas) >= 2:
                preguntas = [
                    {
                        "id": f"p{i + 1}",
                        "pregunta": str(p["pregunta"])[:600],
                        "enfoque": str(p.get("enfoque") or "DISENO")[:20],
                        "archivo": str(p.get("archivo") or "main.py")[:120],
                    }
                    for i, p in enumerate(crudas)
                ]
                rubrica = [
                    {"id": f"p{i + 1}", "puntos_clave": [str(x)[:200] for x in (p.get("puntos_clave") or [])][:4]}
                    for i, p in enumerate(crudas)
                ]
                modelo = cliente.etiqueta
        except Exception as error:  # noqa: BLE001
            log.warning("no se pudieron generar preguntas con el modelo", extra={"causa": type(error).__name__})

    if preguntas is None:
        preguntas = _preguntas_plantilla(archivos)

    defensa = Defensa(
        entrega_id=entrega.id,
        estado="PENDIENTE",
        modelo=modelo,
        preguntas=json.dumps(preguntas, ensure_ascii=False),
        rubrica_privada=json.dumps(rubrica, ensure_ascii=False),
    )
    db.add(defensa)
    db.flush()
    return defensa


def responder(db: Session, defensa: Defensa, respuestas: list[dict], cliente=None) -> Defensa:
    if defensa.estado != "PENDIENTE":
        raise ErrorDominio("DEFENSA_YA_RESPONDIDA", "Esta defensa ya fue respondida.", http=409)

    preguntas = json.loads(defensa.preguntas)
    esperadas = {p["id"] for p in preguntas}
    recibidas = {r["pregunta_id"]: r["respuesta"].strip() for r in respuestas}
    if set(recibidas) != esperadas or len(recibidas) != len(respuestas):
        raise ErrorDominio(
            "RESPUESTAS_INCOMPLETAS",
            "Hay que responder exactamente una vez a cada pregunta de la defensa.",
            http=422,
            detalles={"esperadas": sorted(esperadas)},
        )

    defensa.respuestas = json.dumps(recibidas, ensure_ascii=False)
    defensa.momento_respuesta = ahora()
    cliente = cliente or llm.obtener_cliente()
    rubrica = json.loads(defensa.rubrica_privada or "[]")

    datos = None
    if cliente.disponible:
        archivos = _archivos(db, defensa.entrega)
        bloques = "\n\n".join(
            f"[{p['id']}] Pregunta: {p['pregunta']}\nPuntos clave: "
            f"{next((r['puntos_clave'] for r in rubrica if r['id'] == p['id']), [])}\n"
            f"Respuesta del estudiante: {recibidas[p['id']][:1500]}"
            for p in preguntas
        )
        try:
            datos = cliente.json(
                INSTRUCCIONES_CALIFICACION + llm.AVISO_CODIGO,
                f"{bloques}\n\nCodigo entregado:\n{llm.codigo_para_prompt(archivos, 14000)}",
                max_tokens=1000,
                temperatura=0.1,
            )
        except Exception as error:  # noqa: BLE001
            log.warning("el modelo no califico la defensa", extra={"causa": type(error).__name__})

    if not datos:
        defensa.estado = "SIN_CALIFICAR"
        defensa.retroalimentacion = (
            "Respuestas guardadas. No habia un modelo de lenguaje disponible para calificarlas, asi que "
            "no se asigna puntaje: no se afirma comprension que nadie evaluo."
        )
        db.flush()
        return defensa

    notas = {}
    for c in datos.get("calificaciones") or []:
        if isinstance(c, dict) and c.get("id") in esperadas:
            notas[c["id"]] = {
                "puntaje": llm.acotar(c.get("puntaje")) or 0,
                "comentario": str(c.get("comentario") or "")[:400],
            }
    for pid in esperadas:
        notas.setdefault(pid, {"puntaje": 0, "comentario": "Sin calificacion del modelo para esta respuesta."})
        # Una respuesta de pocas palabras no se puede defender, diga lo que diga el modelo.
        if len(recibidas[pid].split()) < 8:
            notas[pid]["puntaje"] = min(notas[pid]["puntaje"], 20)

    defensa.calificaciones = json.dumps(notas, ensure_ascii=False)
    defensa.puntaje = round(sum(n["puntaje"] for n in notas.values()) / len(notas))
    defensa.aprobada = defensa.puntaje >= UMBRAL_APROBACION
    defensa.retroalimentacion = str(datos.get("retroalimentacion") or "")[:1200] or None
    defensa.estado = "CALIFICADA"
    defensa.modelo = cliente.etiqueta
    db.flush()
    return defensa


def a_dict(defensa: Defensa) -> dict:
    return {
        "id": defensa.id,
        "entrega_id": defensa.entrega_id,
        "estado": defensa.estado,
        "modelo": defensa.modelo,
        "momento_creacion": defensa.momento_creacion,
        "momento_respuesta": defensa.momento_respuesta,
        "preguntas": json.loads(defensa.preguntas),
        "respuestas": json.loads(defensa.respuestas) if defensa.respuestas else None,
        "calificaciones": json.loads(defensa.calificaciones) if defensa.calificaciones else None,
        "puntaje": defensa.puntaje,
        "aprobada": defensa.aprobada,
        "umbral_aprobacion": UMBRAL_APROBACION,
        "retroalimentacion": defensa.retroalimentacion,
    }


def mejor_defensa(db: Session, entrega_id: uuid.UUID) -> Defensa | None:
    return db.scalar(
        select(Defensa)
        .where(Defensa.entrega_id == entrega_id, Defensa.estado == "CALIFICADA")
        .order_by(Defensa.puntaje.desc())
        .limit(1)
    )
