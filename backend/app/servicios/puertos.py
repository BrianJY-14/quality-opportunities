"""Interfaces de integracion del diagrama de clases.

`PreparadorIA` y `EvaluadorAislado` son los dos clasificadores `<<interface>>` del UML.
Los servicios dependen de estas firmas, nunca de una implementacion concreta.
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.dominio.enums import CategoriaPrueba, CondicionEjecucion


@dataclass
class PruebaPropuesta:
    nombre: str
    categoria: CategoriaPrueba
    obligatoria: bool
    condicion_aprobacion: str
    referencia_ejecutable: str
    limite_ejecucion_ms: int | None = None
    # Propuesta de comprobacion ejecutable. Es un BORRADOR como todo lo demas: la revision humana
    # debe validarla contra una solucion de referencia antes de publicar (seccion 5, R4).
    contenido_ejecutable: str | None = None


@dataclass
class BorradorReto:
    """Salida del preparador. RN-ING-02: es un borrador; publicar exige revision humana."""

    titulo: str
    descripcion_publica: str
    criterios_aceptacion: str
    repositorio_base: str | None
    version_base: str | None
    pruebas: list[PruebaPropuesta]
    modelo: str
    version_instrucciones: str
    resumen_preparacion: str
    dificultad: str | None = None
    aptitudes: list[str] = field(default_factory=list)
    # Proyecto inicial que recibe el estudiante al abrir el editor: [{"ruta", "contenido"}].
    proyecto_base: list[dict] | None = None


class PreparadorIA(Protocol):
    """Contrato para proponer un borrador a partir de material privado.

    No concede permisos ni publica directamente."""

    def proponer(self, titulo_original: str, contenido: str) -> BorradorReto: ...


@dataclass
class ResultadoEjecutado:
    prueba_id: object
    condicion_ejecucion: CondicionEjecucion
    aprobada: bool | None = None
    valor_observado: float | None = None
    unidad: str | None = None
    duracion_ms: int | None = None
    detalle: str | None = None


@dataclass
class SalidaEvaluador:
    version_evaluador: str
    resultados: list[ResultadoEjecutado] = field(default_factory=list)


class FalloEvaluador(Exception):
    """Falla de infraestructura del evaluador.

    RN-EVAL-03 exige distinguirla de una solucion desaprobada: se comunica a
    ServicioEvaluacion, que deja la evaluacion en ERROR_TECNICO y sin dictamen."""


class EvaluadorAislado(Protocol):
    """Contrato para ejecutar la fuente entregada frente a las pruebas.

    `archivos` es el proyecto del espacio de trabajo, `[{"ruta", "contenido"}]`, cuando existe.
    Es opcional para que una implementacion que no ejecute codigo pueda ignorarlo: el evaluador
    simulado deriva su resultado del commit y no lo mira.
    """

    def ejecutar(
        self, repositorio: str, commit: str, pruebas: list, archivos: list | None = None
    ) -> SalidaEvaluador: ...
