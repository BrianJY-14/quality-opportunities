"""Evaluador real sobre un sandbox de E2B.

A diferencia de `evaluador_simulado.py`, este ejecuta de verdad: escribe los archivos del espacio
de trabajo dentro de un sandbox aislado y deriva cada resultado del codigo de salida del proceso
y de una duracion medida con reloj. Nada sale de un hash.

La version `e2b:v1` viaja en `Evaluacion.version_evaluador`, en la credencial y en
`/api/v1/meta`, igual que la del simulado: quien lea un resultado sabe con que motor se produjo.

Separacion que sostiene todo lo demas: el proyecto del estudiante se escribe en RAIZ y las
comprobaciones oficiales en OFICIAL, dos carpetas distintas. La comprobacion se ejecuta desde
OFICIAL y su codigo procede de `Prueba.contenido_ejecutable`, que pertenece al reto. Si la
prueba se cargara del proyecto entregado, bastaria con entregar una que apruebe siempre. Por eso
tampoco se pasa `--noconftest` como adorno: sin el, un `conftest.py` del alumno se cargaria en el
proceso que lo califica.

El interprete arranca con OFICIAL como directorio de trabajo, de modo que sys.path no incluye el
codigo del alumno: un archivo suyo llamado `pytest.py` no puede suplantar a la libreria. La ruta
del proyecto viaja en la variable PROYECTO_DIR y cada prueba oficial decide cuando importarlo:

    import os, sys
    sys.path.insert(0, os.environ["PROYECTO_DIR"])
    from main import procesar

Requisitos: `pip install e2b-code-interpreter` y la variable `E2B_API_KEY`. Si falta cualquiera
de las dos, si el sandbox no arranca o si la red falla, se levanta `FalloEvaluador` y la
evaluacion queda en ERROR_TECNICO sin dictamen. RN-EVAL-03 exige no cargarle al estudiante un
fallo del entorno.
"""

import contextlib
import time

from app.core.config import get_settings
from app.dominio.enums import CategoriaPrueba, CondicionEjecucion
from app.servicios.puertos import FalloEvaluador, ResultadoEjecutado, SalidaEvaluador

VERSION = "e2b:v1"
RAIZ = "/home/user/proyecto"  # lo que entrego el estudiante
OFICIAL = "/home/user/oficial"  # las comprobaciones del reto, que el estudiante no controla
SEGUNDOS_SANDBOX = 180  # vida maxima del sandbox; la facturacion es por segundo
SEGUNDOS_CREACION = 45  # espera maxima para obtener un sandbox listo
SEGUNDOS_COMANDO = 30  # techo por comando, aunque el reto declare un limite mayor


def _correr(sandbox, comando: str, timeout: float, cwd: str = RAIZ, envs: dict | None = None):
    """Ejecuta un comando y devuelve su resultado incluso cuando falla.

    `sandbox.commands.run` levanta `CommandExitException` en cuanto el codigo de salida no es
    cero, y una prueba que no pasa es el caso normal de un estudiante que todavia no aprueba,
    no una averia del entorno. Esa excepcion hereda de `CommandResult`, asi que trae los mismos
    campos (`exit_code`, `stdout`, `stderr`) y se devuelve tal cual. Sin esto, cualquier
    desaprobacion terminaria como ERROR_TECNICO y el alumno no veria por que fallo.
    """
    from e2b.sandbox.commands.command_handle import CommandExitException

    try:
        return sandbox.commands.run(comando, cwd=cwd, timeout=timeout, envs=envs)
    except CommandExitException as salida:
        return salida


def _sin_ejecutar(pruebas: list, motivo: str) -> SalidaEvaluador:
    """Sin contenido que ejecutar no se inventa un veredicto: las pruebas quedan NO_EJECUTADA."""
    return SalidaEvaluador(
        version_evaluador=VERSION,
        resultados=[
            ResultadoEjecutado(
                prueba_id=prueba.id,
                condicion_ejecucion=CondicionEjecucion.NO_EJECUTADA,
                detalle=motivo,
            )
            for prueba in pruebas
        ],
    )


class EvaluadorE2B:
    """Implementacion del puerto `EvaluadorAislado` que ejecuta en infraestructura real.

    `archivos` es la lista `[{"ruta", "contenido"}]` del espacio de trabajo. Llega como parametro
    opcional para que el evaluador simulado y las pruebas existentes sigan funcionando sin
    cambios: el simulado lo ignora.
    """

    def ejecutar(
        self,
        repositorio: str,
        commit: str,
        pruebas: list,
        archivos: list | None = None,
    ) -> SalidaEvaluador:
        if not archivos:
            return _sin_ejecutar(pruebas, "El espacio de trabajo esta vacio: no hay codigo que ejecutar.")

        try:
            from e2b_code_interpreter import Sandbox
        except ImportError as error:
            raise FalloEvaluador("El SDK de E2B no esta instalado (pip install e2b-code-interpreter).") from error

        clave = get_settings().E2B_API_KEY
        if not clave:
            raise FalloEvaluador("Falta la variable de entorno E2B_API_KEY.")

        try:
            # `timeout` es la vida del sandbox; `request_timeout` acota cada llamada HTTP al proveedor.
            # Sin el segundo, una creacion que se queda esperando la imagen bloquea el hilo para
            # siempre y la evaluacion no sale nunca de EN_EJECUCION.
            sandbox = Sandbox.create(api_key=clave, timeout=SEGUNDOS_SANDBOX, request_timeout=SEGUNDOS_CREACION)
        except Exception as error:
            raise FalloEvaluador(f"El sandbox no arranco: {type(error).__name__}") from error

        try:
            return self._evaluar(sandbox, archivos, pruebas)
        except FalloEvaluador:
            raise
        except Exception as error:
            raise FalloEvaluador(f"Fallo del entorno de ejecucion: {type(error).__name__}") from error
        finally:
            # Cerrarlo cuanto antes: la facturacion corre por segundo de sandbox vivo.
            with contextlib.suppress(Exception):
                sandbox.kill()

    def _evaluar(self, sandbox, archivos: list, pruebas: list) -> SalidaEvaluador:
        self._escribir_proyecto(sandbox, archivos)
        sandbox.files.make_dir(OFICIAL)

        # Comprobacion previa: si el proyecto no compila, ninguna comprobacion puede aprobar y el
        # motivo es del codigo entregado, no del entorno. Por eso queda EJECUTADA y no aprobada.
        compilacion = _correr(sandbox, "python -m compileall -q .", SEGUNDOS_COMANDO)
        if compilacion.exit_code != 0:
            detalle = (compilacion.stderr or compilacion.stdout or "").strip()[:500]
            return SalidaEvaluador(
                version_evaluador=VERSION,
                resultados=[
                    ResultadoEjecutado(
                        prueba_id=prueba.id,
                        condicion_ejecucion=CondicionEjecucion.EJECUTADA,
                        aprobada=False,
                        detalle=f"El proyecto no compila. {detalle}",
                    )
                    for prueba in pruebas
                ],
            )

        return SalidaEvaluador(
            version_evaluador=VERSION,
            resultados=[self._una_prueba(sandbox, prueba) for prueba in pruebas],
        )

    def _escribir_proyecto(self, sandbox, archivos: list) -> None:
        """Vuelca el proyecto entregado en RAIZ.

        Las rutas ya vienen validadas por `schemas/workspace.py`: relativas, sin `..` y con
        extension admitida, asi que no pueden salir de RAIZ ni alcanzar OFICIAL.
        """
        sandbox.files.make_dir(RAIZ)
        for archivo in archivos:
            ruta = archivo["ruta"]
            destino = f"{RAIZ}/{ruta}"
            if "/" in ruta:
                sandbox.files.make_dir(destino.rsplit("/", 1)[0])
            sandbox.files.write(destino, archivo["contenido"])

    def _una_prueba(self, sandbox, prueba) -> ResultadoEjecutado:
        from e2b.exceptions import TimeoutException

        # Se escribe el codigo tal cual quedo publicado; `strip` solo decide si esta vacio.
        codigo = getattr(prueba, "contenido_ejecutable", None) or ""
        if not codigo.strip():
            # El reto no trae comprobacion ejecutable. No se ejecuta nada del proyecto para
            # rellenar el hueco: eso permitiria al estudiante calificarse a si mismo.
            return ResultadoEjecutado(
                prueba_id=prueba.id,
                condicion_ejecucion=CondicionEjecucion.NO_EJECUTADA,
                detalle="El reto no define el codigo de esta comprobacion.",
            )

        # El nombre lo fija el servidor a partir del identificador: nada de la entrada del
        # usuario llega a formar parte de un comando.
        nombre = f"prueba_{prueba.id.hex}.py"
        sandbox.files.write(f"{OFICIAL}/{nombre}", codigo)

        limite_s = min((prueba.limite_ejecucion_ms or SEGUNDOS_COMANDO * 1000) / 1000, SEGUNDOS_COMANDO)
        inicio = time.perf_counter()
        try:
            salida = _correr(
                sandbox,
                f"python -m pytest --noconftest -q {nombre}",
                limite_s,
                cwd=OFICIAL,
                envs={"PROYECTO_DIR": RAIZ},
            )
        except TimeoutException:
            # Agotar el limite es un resultado sobre la solucion, no una falla de infraestructura.
            return ResultadoEjecutado(
                prueba_id=prueba.id,
                condicion_ejecucion=CondicionEjecucion.EJECUTADA,
                aprobada=False,
                duracion_ms=int(limite_s * 1000),
                detalle=f"La comprobacion no termino dentro del limite de {int(limite_s * 1000)} ms.",
            )
        duracion = int((time.perf_counter() - inicio) * 1000)

        aprobada = salida.exit_code == 0
        if aprobada and prueba.limite_ejecucion_ms:
            aprobada = duracion <= prueba.limite_ejecucion_ms

        valor = unidad = None
        if prueba.categoria == CategoriaPrueba.RENDIMIENTO:
            valor, unidad = float(duracion), "ms"  # medicion real del proceso, no una estimacion

        return ResultadoEjecutado(
            prueba_id=prueba.id,
            condicion_ejecucion=CondicionEjecucion.EJECUTADA,
            aprobada=aprobada,
            valor_observado=valor,
            unidad=unidad,
            duracion_ms=duracion,
            detalle=None if aprobada else (salida.stdout or salida.stderr or "").strip()[-500:],
        )
