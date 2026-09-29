"""Cliente de modelo de lenguaje sobre la API `/chat/completions` compatible con OpenAI.

Un solo cliente sirve para Groq, Gemini (endpoint OpenAI-compatible), OpenRouter u OpenAI: solo
cambian `LLM_BASE_URL` y `LLM_MODEL`. Todas las funciones de IA de la plataforma (preparador de
retos, juez de codigo, tutor, defensa tecnica y resumen del CV) pasan por aqui, de modo que:

- la clave vive en un unico lugar y nunca se registra en logs;
- toda respuesta se pide y se valida como JSON;
- un fallo del proveedor se traduce en `FalloLLM`, que cada servicio convierte en su respaldo
  por reglas en vez de dejar al usuario sin respuesta.

Las pruebas automaticas sustituyen el cliente con `establecer_cliente(doble)`: ninguna prueba
sale a la red ni gasta cuota.
"""

import json
import logging
import re
import time

import httpx

from app.core.config import get_settings

log = logging.getLogger("llm")


class FalloLLM(Exception):
    """El proveedor no respondio, respondio con error o devolvio algo que no es JSON valido."""


class ClienteLLM:
    def __init__(self, api_key: str, base_url: str, modelo: str, timeout_s: float = 40.0):
        self._api_key = api_key
        self._url = base_url.rstrip("/") + "/chat/completions"
        self.modelo = modelo
        self._timeout = timeout_s

    @property
    def disponible(self) -> bool:
        return bool(self._api_key)

    @property
    def etiqueta(self) -> str:
        """Lo que se guarda como `modelo` en cada resultado: proveedor y modelo exactos."""
        proveedor = re.sub(r"^https?://(api\.)?", "", self._url).split("/")[0]
        return f"{proveedor}:{self.modelo}"[:120]

    def json(self, sistema: str, usuario: str, *, max_tokens: int = 1800, temperatura: float = 0.2) -> dict:
        """Pide una respuesta JSON y la devuelve ya decodificada.

        Reintenta una vez ante 429 o 5xx, que en capas gratuitas son habituales y pasajeros.
        """
        if not self.disponible:
            raise FalloLLM("sin clave configurada")

        cuerpo = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            "temperature": temperatura,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        cabeceras = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

        ultimo_error = "sin respuesta"
        for intento in range(2):
            try:
                r = httpx.post(self._url, json=cuerpo, headers=cabeceras, timeout=self._timeout)
            except httpx.HTTPError as error:
                ultimo_error = type(error).__name__
                time.sleep(1.5)
                continue
            if r.status_code in (429, 500, 502, 503, 504) and intento == 0:
                ultimo_error = f"HTTP {r.status_code}"
                time.sleep(2.0)
                continue
            if r.status_code == 400 and "json_validate_failed" in r.text and intento == 0:
                # Groq rechaza con 400 la salida del modo JSON si el modelo la trunca o la rompe.
                # Se reintenta sin el modo estricto: `extraer_json` recupera el objeto del texto.
                ultimo_error = "HTTP 400 json_validate_failed"
                cuerpo.pop("response_format", None)
                continue
            if r.status_code >= 400:
                # El cuerpo de error del proveedor puede ser util, pero nunca incluye la clave.
                raise FalloLLM(f"HTTP {r.status_code}: {r.text[:200]}")
            try:
                contenido = r.json()["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as error:
                raise FalloLLM("respuesta del proveedor con forma inesperada") from error
            return extraer_json(contenido)

        raise FalloLLM(ultimo_error)


def extraer_json(texto: str) -> dict:
    """Decodifica el JSON aunque el modelo lo envuelva en ```json ... ``` o anada texto."""
    if texto is None:
        raise FalloLLM("respuesta vacia")
    limpio = texto.strip()
    limpio = re.sub(r"^```(?:json)?\s*|\s*```$", "", limpio)
    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError:
        inicio, fin = limpio.find("{"), limpio.rfind("}")
        if inicio == -1 or fin <= inicio:
            raise FalloLLM("la respuesta no contiene JSON") from None
        try:
            datos = json.loads(limpio[inicio : fin + 1])
        except json.JSONDecodeError as error:
            raise FalloLLM("JSON invalido en la respuesta") from error
    if not isinstance(datos, dict):
        raise FalloLLM("se esperaba un objeto JSON")
    return datos


_cliente: ClienteLLM | None = None


def obtener_cliente() -> ClienteLLM:
    global _cliente
    if _cliente is None:
        s = get_settings()
        _cliente = ClienteLLM(s.LLM_API_KEY, s.LLM_BASE_URL, s.LLM_MODEL, s.LLM_TIMEOUT_S)
    return _cliente


def establecer_cliente(cliente) -> None:
    """Inyecta un cliente (o un doble de pruebas). `None` vuelve a leer la configuracion."""
    global _cliente
    _cliente = cliente


def codigo_para_prompt(archivos: list[dict], limite: int | None = None) -> str:
    """Serializa el proyecto como texto con cabeceras por archivo, recortado al limite."""
    limite = limite or get_settings().LLM_MAX_CODIGO
    partes, usado = [], 0
    for a in sorted(archivos, key=lambda x: x.get("ruta", "")):
        bloque = f"### {a.get('ruta')}\n{a.get('contenido', '')}\n"
        if usado + len(bloque) > limite:
            partes.append(f"### {a.get('ruta')}\n[recortado: el proyecto supera el limite enviado al modelo]\n")
            break
        partes.append(bloque)
        usado += len(bloque)
    return "\n".join(partes)


def acotar(valor, minimo: int = 0, maximo: int = 100) -> int | None:
    try:
        return max(minimo, min(maximo, round(float(valor))))
    except (TypeError, ValueError):
        return None
