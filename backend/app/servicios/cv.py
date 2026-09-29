"""CV dinamico: grafo de aptitudes, rango y ranking a partir de evidencia verificable.

Nada de lo que aparece aqui lo escribe el estudiante. Cada aptitud del grafo apunta a las
credenciales que la sustentan, y cada credencial a su evaluacion, al juez IA y a la defensa:

    perfil -> aptitud -> credencial (reto, organizacion, puntajes)

Solo cuentan credenciales VIGENTES: revocar una la retira del CV y del ranking en el acto,
porque todo se deriva en cada consulta y nada de esto se persiste (RN-CRED-04).

El unico texto generado que se guarda es el resumen profesional del LLM, con su fecha, y se
construye solo a partir de esta misma evidencia.
"""

import json
import logging
import math
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.dominio import rangos
from app.dominio.enums import VisibilidadPerfil
from app.models import Credencial, Participacion, PerfilEstudiante, RevisionIA
from app.models._base import ahora
from app.servicios import defensa_ia, juez_ia, llm

log = logging.getLogger("cv")
settings = get_settings()


def _lista_json(texto: str | None) -> list:
    try:
        valor = json.loads(texto or "[]")
        return valor if isinstance(valor, list) else []
    except json.JSONDecodeError:
        return []


def evidencias(db: Session, perfil: PerfilEstudiante) -> list[dict]:
    """Una fila por credencial vigente, con todo lo que la respalda."""
    credenciales = db.scalars(
        select(Credencial)
        .join(Participacion, Credencial.participacion_id == Participacion.id)
        .where(Participacion.perfil_usuario_id == perfil.usuario_id)
        .order_by(Credencial.momento_emision.desc())
    ).all()

    filas = []
    for c in credenciales:
        if not c.esta_vigente():
            continue
        evaluacion = c.evaluacion
        reto = c.participacion.reto
        revision = db.get(RevisionIA, evaluacion.id)
        defensa = defensa_ia.mejor_defensa(db, evaluacion.entrega_id)
        puntaje_defensa = defensa.puntaje if defensa and defensa.aprobada else None
        puntaje_revision = revision.puntaje_global if revision else None
        filas.append(
            {
                "identificador_publico": c.identificador_publico,
                "url_verificacion": f"{settings.URL_BASE_VERIFICACION}/{c.identificador_publico}",
                "momento_emision": c.momento_emision,
                "reto_id": reto.id,
                "reto": reto.titulo,
                "dificultad": reto.dificultad,
                "organizacion": reto.organizacion.nombre,
                "organizacion_logo": reto.organizacion.logo,
                "aptitudes_reto": _lista_json(reto.aptitudes),
                "version_evaluador": evaluacion.version_evaluador,
                "huella_proyecto": evaluacion.entrega.huella_proyecto,
                "revision_ia": juez_ia.a_dict(revision),
                "defensa": (
                    {"puntaje": defensa.puntaje, "aprobada": defensa.aprobada, "modelo": defensa.modelo}
                    if defensa
                    else None
                ),
                "xp": rangos.xp_credencial(reto.dificultad, puntaje_revision, puntaje_defensa),
            }
        )
    return filas


def _grafo(filas: list[dict], nombre: str) -> tuple[list[dict], dict]:
    """Agrega aptitudes con su nivel y construye nodos y aristas del grafo."""
    puntos: dict[str, float] = defaultdict(float)
    evidencias_por: dict[str, list[dict]] = defaultdict(list)
    nombres: dict[str, str] = {}

    for f in filas:
        calidad = (f["revision_ia"] or {}).get("puntaje_global") or 70
        vistas = set()
        fuentes = [(a, 1.0, "Aptitud declarada por el reto") for a in f["aptitudes_reto"]]
        fuentes += [
            (a.get("nombre"), 0.6, a.get("evidencia") or "Detectada por el Juez IA")
            for a in (f["revision_ia"] or {}).get("aptitudes", [])
            if isinstance(a, dict)
        ]
        for apt, peso, evidencia in fuentes:
            if not apt:
                continue
            clave = str(apt).strip().lower()
            if clave in vistas:
                continue
            vistas.add(clave)
            nombres.setdefault(clave, str(apt).strip())
            puntos[clave] += peso * calidad / 100
            evidencias_por[clave].append(
                {
                    "credencial": f["identificador_publico"],
                    "reto": f["reto"],
                    "organizacion": f["organizacion"],
                    "evidencia": evidencia,
                }
            )

    aptitudes = sorted(
        (
            {
                "nombre": nombres[k],
                # Satura: la primera evidencia pesa mucho, la quinta sobre lo mismo poco (README: valor marginal decreciente).
                "nivel": round(100 * (1 - math.exp(-p / 1.2))),
                "evidencias": evidencias_por[k],
            }
            for k, p in puntos.items()
        ),
        key=lambda a: (-a["nivel"], a["nombre"]),
    )

    nodos = [{"id": "perfil", "tipo": "PERFIL", "etiqueta": nombre, "valor": None}]
    aristas = []
    for a in aptitudes[:14]:
        aid = f"apt:{a['nombre'].lower()}"
        nodos.append({"id": aid, "tipo": "APTITUD", "etiqueta": a["nombre"], "valor": a["nivel"]})
        aristas.append({"origen": "perfil", "destino": aid})
        for e in a["evidencias"]:
            cid = f"cred:{e['credencial']}"
            if not any(n["id"] == cid for n in nodos):
                nodos.append({"id": cid, "tipo": "EVIDENCIA", "etiqueta": e["reto"], "valor": e["organizacion"]})
            aristas.append({"origen": aid, "destino": cid})
    return aptitudes, {"nodos": nodos, "aristas": aristas}


def construir(db: Session, perfil: PerfilEstudiante) -> dict:
    filas = evidencias(db, perfil)
    aptitudes, grafo = _grafo(filas, perfil.nombre_publico)
    xp = sum(f["xp"] for f in filas)

    dims: dict[str, list[int]] = defaultdict(list)
    for f in filas:
        for k, v in ((f["revision_ia"] or {}).get("dimensiones") or {}).items():
            if v is not None:
                dims[k].append(v)
    revisiones = [
        f["revision_ia"]["puntaje_global"]
        for f in filas
        if f["revision_ia"] and f["revision_ia"]["puntaje_global"] is not None
    ]
    defensas = [f["defensa"]["puntaje"] for f in filas if f["defensa"] and f["defensa"]["puntaje"] is not None]
    participaciones = (
        db.scalar(
            select(func.count()).select_from(Participacion).where(Participacion.perfil_usuario_id == perfil.usuario_id)
        )
        or 0
    )

    return {
        "nombre_publico": perfil.nombre_publico,
        "biografia": perfil.biografia,
        "universidad": perfil.universidad,
        "carrera": perfil.carrera,
        "ciclo": perfil.ciclo,
        "visibilidad": perfil.visibilidad,
        "rango": rangos.rango_para(xp),
        "metricas": {
            "credenciales_vigentes": len(filas),
            "retos_intentados": participaciones,
            "organizaciones": len({f["organizacion"] for f in filas}),
            "promedio_juez_ia": round(sum(revisiones) / len(revisiones)) if revisiones else None,
            "promedio_defensa": round(sum(defensas) / len(defensas)) if defensas else None,
        },
        "dimensiones": {k: round(sum(v) / len(v)) for k, v in dims.items()},
        "aptitudes": aptitudes,
        "grafo": grafo,
        "evidencias": filas,
        "resumen_ia": perfil.resumen_ia,
        "momento_resumen": perfil.momento_resumen,
    }


INSTRUCCIONES_RESUMEN = """Redactas el resumen profesional de un CV tecnico verificable. Recibes SOLO evidencia comprobada:
retos certificados, puntajes de un juez de codigo, defensas tecnicas y aptitudes con su nivel.

Reglas:
- 3 o 4 frases, maximo 90 palabras, en tercera persona impersonal (sin "yo" ni "tu").
- Cita retos u organizaciones concretas y cifras que aparezcan en la evidencia.
- No inventes experiencia, empresas, tecnologias ni logros que no esten en la evidencia.
- Tono sobrio, sin adjetivos grandilocuentes, sin emojis ni frases publicitarias.
- Si la evidencia es escasa, dilo con naturalidad (perfil en formacion).

Devuelve UNICAMENTE: {"resumen": "texto"}"""


def generar_resumen(db: Session, perfil: PerfilEstudiante, cliente=None) -> PerfilEstudiante:
    from app.core.errors import ErrorDominio

    cliente = cliente or llm.obtener_cliente()
    if not cliente.disponible:
        raise ErrorDominio(
            "LLM_NO_CONFIGURADO", "El servidor no tiene un modelo de lenguaje configurado (LLM_API_KEY).", http=503
        )
    cv = construir(db, perfil)
    evidencia = {
        "carrera": cv["carrera"],
        "universidad": cv["universidad"],
        "ciclo": cv["ciclo"],
        "rango": cv["rango"]["nombre"],
        "metricas": cv["metricas"],
        "dimensiones_promedio": cv["dimensiones"],
        "aptitudes": [{"nombre": a["nombre"], "nivel": a["nivel"]} for a in cv["aptitudes"][:10]],
        "retos": [
            {
                "reto": f["reto"],
                "organizacion": f["organizacion"],
                "dificultad": f["dificultad"],
                "juez_ia": (f["revision_ia"] or {}).get("puntaje_global"),
                "defensa": (f["defensa"] or {}).get("puntaje"),
            }
            for f in cv["evidencias"]
        ],
    }
    from app.servicios.llm import FalloLLM

    try:
        datos = cliente.json(
            INSTRUCCIONES_RESUMEN, json.dumps(evidencia, ensure_ascii=False, default=str), max_tokens=400
        )
    except FalloLLM as error:
        raise ErrorDominio(
            "LLM_NO_DISPONIBLE", "El modelo de lenguaje no respondio. Intenta de nuevo.", http=503
        ) from error
    resumen = str(datos.get("resumen") or "").strip()
    if not resumen:
        raise ErrorDominio("LLM_NO_DISPONIBLE", "El modelo devolvio un resumen vacio.", http=503)
    perfil.resumen_ia = resumen[:1200]
    perfil.momento_resumen = ahora()
    db.flush()
    return perfil


def ranking(db: Session, limite: int = 50) -> list[dict]:
    """Solo perfiles publicos con al menos una credencial vigente (DECISION V1 de visibilidad)."""
    perfiles = db.scalars(
        select(PerfilEstudiante).where(PerfilEstudiante.visibilidad == VisibilidadPerfil.PUBLICO)
    ).all()
    filas = []
    for p in perfiles:
        ev = evidencias(db, p)
        if not ev:
            continue
        xp = sum(f["xp"] for f in ev)
        revisiones = [
            f["revision_ia"]["puntaje_global"]
            for f in ev
            if f["revision_ia"] and f["revision_ia"]["puntaje_global"] is not None
        ]
        conteo: dict[str, int] = defaultdict(int)
        for f in ev:
            for a in f["aptitudes_reto"]:
                conteo[a] += 1
        filas.append(
            {
                "nombre_publico": p.nombre_publico,
                "universidad": p.universidad,
                "carrera": p.carrera,
                "xp": xp,
                "rango": rangos.rango_para(xp),
                "credenciales": len(ev),
                "promedio_juez_ia": round(sum(revisiones) / len(revisiones)) if revisiones else None,
                "organizaciones": sorted({f["organizacion"] for f in ev}),
                "aptitudes_top": [a for a, _ in sorted(conteo.items(), key=lambda x: -x[1])[:3]],
                "ultima_emision": max(f["momento_emision"] for f in ev),
            }
        )
    # Desempate estable: XP, luego calidad media, luego quien certifico antes, luego nombre.
    filas.sort(key=lambda f: (-f["xp"], -(f["promedio_juez_ia"] or 0), f["ultima_emision"], f["nombre_publico"]))
    for i, f in enumerate(filas[:limite], start=1):
        f["posicion"] = i
    return filas[:limite]
