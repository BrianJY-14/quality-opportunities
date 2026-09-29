"""Tutor IA del editor: diagnosticos y pistas sobre la revision guardada, sin dar la solucion.

Flujo (seccion U4 del procedimiento):
1. Toma la revision GUARDADA del espacio de trabajo, no lo que el navegador diga tener.
2. Corre el analisis estatico: errores de sintaxis con linea exacta y reglas de riesgo.
3. Con esos diagnosticos, el enunciado y el codigo, pide al modelo pistas socraticas. Las
   instrucciones le prohiben escribir codigo de la solucion, y la salida se filtra: cualquier
   bloque de codigo largo en una pista se descarta.

Sin modelo, responde solo con los diagnosticos estaticos y `modo = "REGLAS"`. La ausencia de
diagnosticos significa "no se detectaron problemas en estas comprobaciones", no "aprobado".

Limite: 6 consultas por minuto por usuario, en memoria del proceso. Suficiente para una instancia;
con varias habria que moverlo a la base o a Redis.
"""

import logging
import re
import time
from collections import defaultdict, deque

from app.core.errors import ErrorDominio
from app.servicios import analisis_estatico, llm

log = logging.getLogger("tutor_ia")

LIMITE_POR_MINUTO = 6
_ventanas: dict[str, deque] = defaultdict(deque)

INSTRUCCIONES = """Eres el Tutor IA de Quality Opportunities. Un estudiante universitario esta resolviendo un reto
tecnico en Python y te pide ayuda. Tu objetivo es que APRENDA, no darle la solucion.

Reglas estrictas:
- NUNCA escribas la solucion ni fragmentos de codigo de mas de una linea.
- Da pistas graduales: primero una pregunta que lo haga pensar, luego el concepto clave.
- Senala archivo y linea cuando puedas.
- Si hay errores de sintaxis, priorizalos.
- Responde en espanol, tono cercano y profesional, sin emojis.

Devuelve UNICAMENTE este JSON:
{
  "diagnosticos": [{"archivo": "main.py", "linea": 12, "severidad": "ERROR | ADVERTENCIA | INFO", "mensaje": "que ocurre", "pista": "pista sin solucion"}],
  "respuesta": "respuesta a la pregunta del estudiante, maximo 120 palabras",
  "siguiente_paso": "una accion concreta para avanzar",
  "conceptos": ["2 a 4 conceptos a repasar"]
}
Maximo 5 diagnosticos."""


def _limitar(usuario_id: str) -> None:
    ahora = time.monotonic()
    ventana = _ventanas[usuario_id]
    while ventana and ahora - ventana[0] > 60:
        ventana.popleft()
    if len(ventana) >= LIMITE_POR_MINUTO:
        espera = int(60 - (ahora - ventana[0])) + 1
        raise ErrorDominio(
            "LIMITE_FRECUENCIA",
            f"Demasiadas consultas al tutor. Intenta de nuevo en {espera} s.",
            http=429,
            detalles={"retry_after": espera},
        )
    ventana.append(ahora)


def _sin_codigo(texto) -> str:
    """Quita bloques de codigo de varias lineas: el tutor no entrega soluciones."""
    texto = str(texto or "")
    return re.sub(r"```[\s\S]*?```", "[fragmento omitido: el tutor no da codigo]", texto)[:800]


def consultar(usuario_id: str, reto, archivos: list[dict], revision: int, pregunta: str | None, cliente=None) -> dict:
    _limitar(usuario_id)
    cliente = cliente or llm.obtener_cliente()
    estatico = analisis_estatico.analizar(archivos)
    diagnosticos = [dict(d.a_dict()) for d in estatico.diagnosticos]

    base = {
        "revision": revision,
        "modo": "REGLAS",
        "modelo": "estatico:v1",
        "diagnosticos": diagnosticos,
        "respuesta": None,
        "siguiente_paso": None,
        "conceptos": [],
        "metricas": estatico.metricas,
        "aviso": "Sin diagnosticos no significa aprobado: solo que estas comprobaciones no hallaron problemas.",
    }

    if not archivos:
        base["respuesta"] = "El proyecto guardado esta vacio. Guarda al menos main.py antes de consultar."
        return base
    if not cliente.disponible:
        return base

    mensaje = (
        f"Reto: {reto.titulo}\nEnunciado: {reto.descripcion_publica[:1500]}\n"
        f"Criterios: {reto.criterios_aceptacion[:800]}\n"
        f"Pruebas del reto: {'; '.join(f'{p.nombre}: {p.condicion_aprobacion}' for p in reto.pruebas)[:1500]}\n\n"
        f"Diagnosticos estaticos ya detectados: {diagnosticos[:10]}\n\n"
        f"Pregunta del estudiante: {(pregunta or 'Revisa mi avance y dime que mejorar.')[:600]}\n\n"
        f"Codigo guardado (revision {revision}):\n{llm.codigo_para_prompt(archivos, 16000)}"
    )
    try:
        datos = cliente.json(INSTRUCCIONES + llm.AVISO_CODIGO, mensaje, max_tokens=1000, temperatura=0.4)
    except Exception as error:  # noqa: BLE001
        log.warning("el tutor IA no respondio", extra={"causa": type(error).__name__})
        base["respuesta"] = "El modelo no respondio ahora; se muestran solo los diagnosticos estaticos."
        return base

    del_modelo = []
    for d in (datos.get("diagnosticos") or [])[:5]:
        if not isinstance(d, dict):
            continue
        severidad = str(d.get("severidad", "INFO")).upper()
        del_modelo.append(
            {
                "archivo": str(d.get("archivo") or "main.py")[:120],
                "linea": d.get("linea") if isinstance(d.get("linea"), int) else None,
                "severidad": severidad if severidad in ("ERROR", "ADVERTENCIA", "INFO") else "INFO",
                "origen": "TUTOR_IA",
                "mensaje": _sin_codigo(d.get("mensaje")),
                "pista": _sin_codigo(d.get("pista")),
            }
        )

    base.update(
        modo="IA",
        modelo=cliente.etiqueta,
        diagnosticos=diagnosticos + del_modelo,
        respuesta=_sin_codigo(datos.get("respuesta")),
        siguiente_paso=_sin_codigo(datos.get("siguiente_paso")),
        conceptos=[str(c)[:60] for c in (datos.get("conceptos") or [])][:4],
    )
    return base
