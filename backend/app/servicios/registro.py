"""Resolucion de los puertos a implementaciones concretas, por variable de entorno."""

from app.core.config import get_settings
from app.servicios.evaluador_e2b import EvaluadorE2B
from app.servicios.evaluador_simulado import EvaluadorSimulado
from app.servicios.preparador_llm import PreparadorLLM
from app.servicios.preparador_reglas import PreparadorPorReglas
from app.servicios.puertos import EvaluadorAislado, PreparadorIA

settings = get_settings()


def obtener_evaluador() -> EvaluadorAislado:
    if settings.EVALUADOR == "simulado":
        return EvaluadorSimulado()
    if settings.EVALUADOR == "e2b":
        return EvaluadorE2B()
    raise NotImplementedError(f"Evaluador no disponible: {settings.EVALUADOR}")


def obtener_preparador() -> PreparadorIA:
    if settings.PREPARADOR == "reglas":
        return PreparadorPorReglas()
    if settings.PREPARADOR == "llm":
        return PreparadorLLM()
    raise NotImplementedError(f"Preparador no disponible: {settings.PREPARADOR}")
