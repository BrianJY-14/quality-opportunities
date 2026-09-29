"""Analisis estatico del proyecto del estudiante, sin ejecutar su codigo.

Se usa `ast.parse`, que solo construye el arbol sintactico: ningun import ni instruccion del
estudiante corre dentro del proceso de FastAPI (seccion U4 del procedimiento).

Produce tres cosas que consumen el juez, el tutor y la defensa:

1. Diagnosticos con archivo y linea (errores de sintaxis, `except:` sin tipo, `eval`...).
2. Metricas deterministas: tamano, funciones, complejidad ciclomatica aproximada, pruebas.
3. Las cuatro reglas puntuables del componente A del procedimiento (seccion 12), 25 puntos cada
   una. Son reglas acotadas de estilo y superficie de riesgo, no una prueba de seguridad.

Estas cifras no dependen de ningun modelo y se muestran siempre junto a lo que diga el LLM, para
que quien lea el informe distinga lo medido de lo opinado.
"""

import ast
from dataclasses import dataclass, field

# Import -> aptitud tecnica visible en el CV. Solo se afirma lo que aparece en el codigo.
STACK = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "redis": "Redis",
    "sqlalchemy": "SQLAlchemy",
    "psycopg2": "PostgreSQL",
    "psycopg": "PostgreSQL",
    "asyncpg": "PostgreSQL",
    "sqlite3": "SQLite",
    "pydantic": "Pydantic",
    "pytest": "Pytest",
    "unittest": "Unit testing",
    "asyncio": "Asyncio",
    "threading": "Concurrencia",
    "multiprocessing": "Concurrencia",
    "concurrent": "Concurrencia",
    "csv": "ETL / CSV",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "hashlib": "Hashing",
    "hmac": "Hashing",
    "re": "Expresiones regulares",
    "httpx": "Clientes HTTP",
    "requests": "Clientes HTTP",
    "aiohttp": "Clientes HTTP",
    "logging": "Logging",
    "dataclasses": "Dataclasses",
    "typing": "Tipado estatico",
    "functools": "Programacion funcional",
    "heapq": "Estructuras de datos",
    "collections": "Estructuras de datos",
    "bisect": "Estructuras de datos",
    "json": "JSON",
    "time": None,
    "os": None,
    "sys": None,
}

_RAMAS = (
    ast.If,
    ast.For,
    ast.While,
    ast.AsyncFor,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.IfExp,
    ast.comprehension,
)

REGLAS = {
    "sin_eval_exec": "Sin llamadas directas a eval() o exec()",
    "sin_pickle": "Sin importar pickle",
    "sin_import_estrella": "Sin 'from modulo import *'",
    "sin_except_desnudo": "Sin 'except:' sin tipo",
}


@dataclass
class Diagnostico:
    archivo: str
    linea: int | None
    severidad: str  # ERROR | ADVERTENCIA | INFO
    origen: str
    mensaje: str
    pista: str

    def a_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Analisis:
    diagnosticos: list[Diagnostico] = field(default_factory=list)
    metricas: dict = field(default_factory=dict)
    reglas: dict = field(default_factory=dict)
    aptitudes: list[str] = field(default_factory=list)

    @property
    def compila(self) -> bool:
        return not any(d.origen == "COMPILACION_PYTHON" for d in self.diagnosticos)

    @property
    def puntaje_reglas(self) -> int:
        """Componente A: 25 puntos por regla cumplida."""
        return 25 * sum(1 for ok in self.reglas.values() if ok)

    def a_dict(self) -> dict:
        return {
            "compila": self.compila,
            "metricas": self.metricas,
            "reglas": [{"id": k, "descripcion": REGLAS[k], "cumple": v} for k, v in self.reglas.items()],
            "puntaje_reglas": self.puntaje_reglas,
            "aptitudes_detectadas": self.aptitudes,
        }


def _complejidad(nodo: ast.AST) -> int:
    total = 1
    for hijo in ast.walk(nodo):
        if isinstance(hijo, _RAMAS):
            total += 1
        elif isinstance(hijo, ast.BoolOp):
            total += len(hijo.values) - 1
    return total


def analizar(archivos: list[dict]) -> Analisis:
    res = Analisis(reglas={k: True for k in REGLAS})
    lineas_codigo = 0
    funciones: list[tuple[str, int, int]] = []  # nombre, lineas, complejidad
    clases = 0
    con_docstring = 0
    con_tipos = 0
    tiene_pruebas = False
    modulos: set[str] = set()

    for a in archivos:
        ruta, contenido = a.get("ruta", ""), a.get("contenido", "") or ""
        if not ruta.endswith(".py"):
            continue
        lineas_codigo += sum(1 for ln in contenido.splitlines() if ln.strip() and not ln.strip().startswith("#"))
        if ruta.split("/")[-1].startswith("test_") or "/tests/" in f"/{ruta}":
            tiene_pruebas = True

        try:
            arbol = ast.parse(contenido, filename=ruta)
        except SyntaxError as error:
            res.diagnosticos.append(
                Diagnostico(
                    ruta,
                    error.lineno,
                    "ERROR",
                    "COMPILACION_PYTHON",
                    f"Error de sintaxis: {error.msg}.",
                    "Revisa parentesis, dos puntos y sangria en esa linea y en la anterior.",
                )
            )
            continue

        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                modulos.update(n.name.split(".")[0] for n in nodo.names)
                if any(n.name.split(".")[0] == "pickle" for n in nodo.names):
                    res.reglas["sin_pickle"] = False
                    res.diagnosticos.append(
                        Diagnostico(
                            ruta,
                            nodo.lineno,
                            "ADVERTENCIA",
                            "REGLA_ESTATICA",
                            "Se importa pickle.",
                            "Deserializar pickle de origen no confiable ejecuta codigo; prefiere JSON.",
                        )
                    )
            elif isinstance(nodo, ast.ImportFrom):
                if nodo.module:
                    modulos.add(nodo.module.split(".")[0])
                    if nodo.module.split(".")[0] == "pickle":
                        res.reglas["sin_pickle"] = False
                if any(n.name == "*" for n in nodo.names):
                    res.reglas["sin_import_estrella"] = False
                    res.diagnosticos.append(
                        Diagnostico(
                            ruta,
                            nodo.lineno,
                            "ADVERTENCIA",
                            "REGLA_ESTATICA",
                            f"Import con asterisco desde '{nodo.module}'.",
                            "Importa solo los nombres que usas: evita colisiones y deja claro el origen.",
                        )
                    )
            elif isinstance(nodo, ast.ExceptHandler) and nodo.type is None:
                res.reglas["sin_except_desnudo"] = False
                res.diagnosticos.append(
                    Diagnostico(
                        ruta,
                        nodo.lineno,
                        "ADVERTENCIA",
                        "REGLA_ESTATICA",
                        "'except:' sin tipo captura tambien KeyboardInterrupt y SystemExit.",
                        "Captura la excepcion concreta que esperas, por ejemplo ValueError.",
                    )
                )
            elif isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id in ("eval", "exec"):
                res.reglas["sin_eval_exec"] = False
                res.diagnosticos.append(
                    Diagnostico(
                        ruta,
                        nodo.lineno,
                        "ERROR",
                        "REGLA_ESTATICA",
                        f"Llamada directa a {nodo.func.id}().",
                        "Ejecutar texto como codigo abre la puerta a inyecciones; busca una alternativa explicita.",
                    )
                )
            elif isinstance(nodo, ast.ClassDef):
                clases += 1
                if ast.get_docstring(nodo):
                    con_docstring += 1
            elif isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef):
                inicio = nodo.lineno
                fin = getattr(nodo, "end_lineno", inicio) or inicio
                cc = _complejidad(nodo)
                funciones.append((nodo.name, fin - inicio + 1, cc))
                if nodo.name.startswith("test_"):
                    tiene_pruebas = True
                if ast.get_docstring(nodo):
                    con_docstring += 1
                if nodo.returns is not None or any(arg.annotation is not None for arg in nodo.args.args):
                    con_tipos += 1
                if cc > 10:
                    res.diagnosticos.append(
                        Diagnostico(
                            ruta,
                            inicio,
                            "INFO",
                            "COMPLEJIDAD",
                            f"La funcion '{nodo.name}' tiene complejidad ciclomatica aproximada {cc}.",
                            "Extrae las ramas en funciones pequenas con un nombre que explique cada decision.",
                        )
                    )

    n_func = len(funciones)
    res.metricas = {
        "lineas_codigo": lineas_codigo,
        "archivos_python": sum(1 for a in archivos if a.get("ruta", "").endswith(".py")),
        "funciones": n_func,
        "clases": clases,
        "lineas_por_funcion": round(sum(f[1] for f in funciones) / n_func, 1) if n_func else None,
        "complejidad_maxima": max((f[2] for f in funciones), default=None),
        "complejidad_media": round(sum(f[2] for f in funciones) / n_func, 1) if n_func else None,
        "funciones_con_tipos_pct": round(100 * con_tipos / n_func) if n_func else None,
        "documentadas_pct": round(100 * con_docstring / (n_func + clases)) if (n_func + clases) else None,
        "tiene_pruebas": tiene_pruebas,
    }

    aptitudes = {STACK[m] for m in modulos if STACK.get(m)}
    if tiene_pruebas:
        aptitudes.add("Pytest" if "pytest" in modulos else "Unit testing")
    res.aptitudes = sorted(aptitudes)
    return res


def dimensiones_heuristicas(analisis: Analisis) -> dict[str, int]:
    """Puntajes por dimension sin modelo. Se usan solo cuando no hay LLM, y se etiquetan asi."""
    m = analisis.metricas
    if not m.get("funciones"):
        base = 40 if analisis.compila else 0
        return {k: base for k in ("arquitectura", "legibilidad", "robustez", "pruebas", "seguridad")}

    cc = m.get("complejidad_media") or 1
    largo = m.get("lineas_por_funcion") or 1
    arquitectura = 90 if largo <= 20 else 75 if largo <= 40 else 55
    arquitectura -= 10 if (m.get("complejidad_maxima") or 0) > 10 else 0
    legibilidad = 50 + (m.get("documentadas_pct") or 0) // 4 + (m.get("funciones_con_tipos_pct") or 0) // 4
    robustez = 85 if analisis.reglas["sin_except_desnudo"] else 60
    robustez -= 0 if cc <= 6 else 10
    pruebas = 85 if m.get("tiene_pruebas") else 35
    seguridad = 40 + 15 * sum(
        1 for k in ("sin_eval_exec", "sin_pickle", "sin_import_estrella", "sin_except_desnudo") if analisis.reglas[k]
    )
    if not analisis.compila:
        arquitectura, robustez = min(arquitectura, 30), min(robustez, 20)
    return {
        "arquitectura": max(0, min(100, arquitectura)),
        "legibilidad": max(0, min(100, legibilidad)),
        "robustez": max(0, min(100, robustez)),
        "pruebas": pruebas,
        "seguridad": min(100, seguridad),
    }
