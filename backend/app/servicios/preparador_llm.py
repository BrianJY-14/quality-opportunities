"""AI Pedagogical Scoper: preparador de retos con modelo de lenguaje.

Implementa el puerto `PreparadorIA`. Recibe el issue privado de una organizacion y propone un
BORRADOR de reto: enunciado publico, criterios, dificultad, aptitudes que ejercita, pruebas con
su codigo pytest propuesto y un proyecto inicial para el editor.

Orden de las operaciones, y por que:

1. **Saneamiento antes de la llamada.** RN-ING-01 exige que el original sea privado. Enviarlo sin
   sanear a un tercero seria incumplirlo, asi que al proveedor solo llega el texto con credenciales,
   IPs internas, correos y cadenas de conexion reemplazados por `[REDACTADO]`.
2. **Llamada al modelo** con salida JSON obligatoria.
3. **Validacion del contrato.** Lo que no encaja (categorias desconocidas, menos de dos pruebas
   obligatorias, rutas raras) se corrige o se descarta; el modelo no decide la forma de los datos.
4. **Segundo saneamiento de la salida.** Si el modelo reprodujo un dato sensible, se vuelve a
   redactar antes de guardarlo.

Si el proveedor falla o no hay clave, se cae a `PreparadorPorReglas`: una caida de red no puede
dejar una solicitud sin borrador. En todos los casos el resultado es un borrador que un
representante revisa antes de publicar (RN-ING-02).
"""

import logging
import re

from app.dominio.enums import CategoriaPrueba
from app.servicios import llm
from app.servicios.preparador_reglas import PreparadorPorReglas, sanear
from app.servicios.puertos import BorradorReto, PruebaPropuesta

log = logging.getLogger("preparador")

VERSION_INSTRUCCIONES = "scoper-2026.09.2"
DIFICULTADES = ("BASICO", "INTERMEDIO", "AVANZADO")
_RUTA_VALIDA = re.compile(r"^[A-Za-z0-9_\-./]{1,120}$")

INSTRUCCIONES = """Eres el AI Pedagogical Scoper de Quality Opportunities, una plataforma donde estudiantes
universitarios resuelven retos tecnicos basados en problemas reales de empresas.

Recibes el material de un issue de una organizacion, YA SANEADO (los datos sensibles aparecen como
[REDACTADO]). Tu tarea es convertirlo en un reto autocontenido en Python que un estudiante de 5.o a
9.o ciclo pueda resolver en un editor web, SIN acceso a sistemas de la empresa.

Devuelve UNICAMENTE un objeto JSON con esta forma:
{
  "titulo": "titulo corto y concreto (max 90 caracteres)",
  "descripcion_publica": "contexto del problema y que se pide, en espanol, sin datos internos de la empresa, max 1500 caracteres",
  "criterios_aceptacion": "condiciones observables que debe cumplir una solucion",
  "dificultad": "BASICO | INTERMEDIO | AVANZADO",
  "aptitudes": ["3 a 6 aptitudes tecnicas que ejercita, p. ej. Concurrencia, Idempotencia, Validacion de datos"],
  "funcion_principal": "nombre de la funcion que el estudiante implementa en main.py",
  "proyecto_base": [
    {"ruta": "main.py", "contenido": "codigo inicial con la firma de la funcion, docstring del contrato y un TODO; NO la solucion"},
    {"ruta": "README.md", "contenido": "instrucciones breves"}
  ],
  "pruebas": [
    {
      "nombre": "nombre de la comprobacion",
      "categoria": "FUNCIONAL | CASO_LIMITE | RENDIMIENTO",
      "obligatoria": true,
      "condicion_aprobacion": "condicion observable y verificable",
      "referencia_ejecutable": "tests/test_nombre.py",
      "codigo_pytest": "codigo pytest completo que importa la funcion con: import os, sys; sys.path.insert(0, os.environ['PROYECTO_DIR']); from main import <funcion>"
    }
  ],
  "resumen_preparacion": "que se adapto del material y que debe revisar el humano antes de publicar"
}

Reglas:
- Entre 4 y 6 pruebas. Al menos dos obligatorias y al menos una de categoria CASO_LIMITE.
- Las pruebas de RENDIMIENTO nunca son obligatorias.
- Cada condicion_aprobacion describe que se comprueba, no una opinion.
- El proyecto_base NO resuelve el reto.
- No inventes nombres de personas, correos, URLs internas ni datos que no esten en el material.
- Puedes mantener el nombre de la organizacion solo si aparece en el material.
- Todo el texto en espanol neutro, sin emojis."""


def _a_categoria(valor) -> CategoriaPrueba:
    try:
        return CategoriaPrueba(str(valor).strip().upper())
    except ValueError:
        return CategoriaPrueba.FUNCIONAL


def _texto(valor, limite: int, respaldo: str = "") -> str:
    if not isinstance(valor, str) or not valor.strip():
        return respaldo
    limpio, _ = sanear(valor.strip())
    return limpio[:limite]


class PreparadorLLM:
    """PreparadorIA sobre un proveedor externo, con respaldo por reglas."""

    def __init__(self, respaldo: PreparadorPorReglas | None = None, cliente=None):
        self._respaldo = respaldo or PreparadorPorReglas()
        self._cliente = cliente

    @property
    def cliente(self):
        return self._cliente or llm.obtener_cliente()

    def proponer(self, titulo_original: str, contenido: str) -> BorradorReto:
        limpio, conteo = sanear(contenido)
        titulo_limpio, _ = sanear(titulo_original)
        detectado = ", ".join(f"{n} {t}" for t, n in conteo.items()) or "ningun elemento sensible"

        if not self.cliente.disponible:
            log.info("preparador sin clave de LLM, se usa el respaldo por reglas")
            return self._respaldo.proponer(titulo_original, contenido)

        try:
            datos = self.cliente.json(
                INSTRUCCIONES,
                f"Titulo del issue: {titulo_limpio}\n\nMaterial saneado:\n{limpio[:12000]}",
                max_tokens=4000,
                temperatura=0.3,
            )
            return self._a_borrador(datos, titulo_limpio, detectado)
        except Exception as error:  # noqa: BLE001 -- cualquier fallo cae al respaldo
            log.warning("el preparador con modelo fallo, se usa el respaldo", extra={"causa": type(error).__name__})
            borrador = self._respaldo.proponer(titulo_original, contenido)
            borrador.resumen_preparacion += f" El modelo de lenguaje no respondio ({type(error).__name__})."
            return borrador

    def _a_borrador(self, datos: dict, titulo: str, detectado: str) -> BorradorReto:
        pruebas: list[PruebaPropuesta] = []
        for i, p in enumerate(datos.get("pruebas") or []):
            if not isinstance(p, dict):
                continue
            categoria = _a_categoria(p.get("categoria"))
            referencia = str(p.get("referencia_ejecutable") or f"tests/test_{i + 1}.py")
            if not _RUTA_VALIDA.match(referencia) or ".." in referencia:
                referencia = f"tests/test_{i + 1}.py"
            codigo = p.get("codigo_pytest")
            pruebas.append(
                PruebaPropuesta(
                    nombre=_texto(p.get("nombre"), 300, f"Prueba {i + 1}"),
                    categoria=categoria,
                    # Regla del contrato: el rendimiento nunca es obligatorio.
                    obligatoria=bool(p.get("obligatoria")) and categoria != CategoriaPrueba.RENDIMIENTO,
                    condicion_aprobacion=_texto(p.get("condicion_aprobacion"), 1000, "Pendiente de revision."),
                    referencia_ejecutable=referencia,
                    limite_ejecucion_ms=5000 if categoria == CategoriaPrueba.RENDIMIENTO else None,
                    contenido_ejecutable=_texto(codigo, 20000) or None,
                )
            )
            if len(pruebas) == 6:
                break

        if len(pruebas) < 3:
            raise ValueError("el modelo propuso menos de tres pruebas")
        # Publicar exige obligatorias: si el modelo marco menos de dos, se promueven las primeras
        # no de rendimiento, y el resumen lo dice para que el revisor lo vea.
        ajustes = []
        while sum(p.obligatoria for p in pruebas) < 2:
            candidata = next(
                (p for p in pruebas if not p.obligatoria and p.categoria != CategoriaPrueba.RENDIMIENTO), None
            )
            if candidata is None:
                break
            candidata.obligatoria = True
            ajustes.append(candidata.nombre)

        proyecto = []
        for a in datos.get("proyecto_base") or []:
            if not isinstance(a, dict):
                continue
            ruta = str(a.get("ruta") or "")
            if _RUTA_VALIDA.match(ruta) and ".." not in ruta and ruta.rsplit(".", 1)[-1] in ("py", "md", "txt", "json"):
                proyecto.append({"ruta": ruta, "contenido": _texto(a.get("contenido"), 30000)})
        dificultad = str(datos.get("dificultad") or "").upper()
        aptitudes = [_texto(x, 40) for x in (datos.get("aptitudes") or []) if isinstance(x, str)][:6]

        resumen = _texto(datos.get("resumen_preparacion"), 1500, "Borrador propuesto por el modelo.")
        resumen = (
            f"Material saneado antes de enviarlo al modelo: {detectado}. {resumen} "
            "Las pruebas en codigo son una propuesta: validarlas contra una solucion de referencia antes de publicar."
        )
        if ajustes:
            resumen += f" Se marcaron como obligatorias para cumplir el minimo: {', '.join(ajustes)}."

        return BorradorReto(
            titulo=_texto(datos.get("titulo"), 200, titulo),
            descripcion_publica=_texto(datos.get("descripcion_publica"), 2000, "Pendiente de redaccion."),
            criterios_aceptacion=_texto(
                datos.get("criterios_aceptacion"), 1500, "Superar todas las pruebas obligatorias."
            ),
            repositorio_base=None,
            version_base=VERSION_INSTRUCCIONES,
            pruebas=pruebas,
            modelo=self.cliente.etiqueta,
            version_instrucciones=VERSION_INSTRUCCIONES,
            resumen_preparacion=resumen,
            dificultad=dificultad if dificultad in DIFICULTADES else "INTERMEDIO",
            aptitudes=[a for a in aptitudes if a],
            proyecto_base=proyecto or None,
        )
