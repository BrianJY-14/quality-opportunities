"""Ampliacion de los datos de demostracion para las funciones de IA.

Lo llama `seed.main()`. Es idempotente: identifica retos por titulo y perfiles por nombre publico,
de modo que se puede ejecutar sobre la base de produccion ya sembrada sin duplicar nada.

Siembra:
1. Dificultad, aptitudes y proyecto inicial para los tres retos originales.
2. Dos organizaciones ficticias y cuatro retos nuevos. Uno ("Registro idempotente de pagos")
   trae comprobaciones pytest reales en `contenido_ejecutable`, de modo que con EVALUADOR=e2b se
   califica ejecutando codigo de verdad.
3. Cinco perfiles de DEMOSTRACION con credenciales, para que el ranking y el CV no aparezcan
   vacios en la presentacion. Sus evaluaciones llevan `version_evaluador = "seed-demo:v1"`: la
   version viaja en la credencial y en la API, asi que nadie puede confundirlas con una ejecucion
   real. El Juez IA de esas entregas es la revision estatica real de su codigo, sin modelo.

Todas las organizaciones y personas son ficticias; no representan marcas reales.
"""

import json

from sqlalchemy import select

from app.core.security import hash_password
from app.dominio.enums import (
    CategoriaPrueba,
    CondicionEjecucion,
    Dictamen,
    EstadoEvaluacion,
    EstadoReto,
    VisibilidadPerfil,
)
from app.models import (
    Entrega,
    Evaluacion,
    Organizacion,
    Participacion,
    PerfilEstudiante,
    Prueba,
    ResultadoPrueba,
    Reto,
    Usuario,
)
from app.models._base import ahora
from app.servicios import certificacion, juez_ia
from app.servicios.llm import ClienteLLM
from app.servicios.workspace import documento_canonico, huella

CLAVE_DEMO = "demo12345"

# --------------------------------------------------------------------------- retos originales

ORIGINALES = {
    "Idempotencia y concurrencia en una pasarela de pagos": (
        "AVANZADO",
        ["Idempotencia", "Concurrencia", "Sistemas transaccionales", "Manejo de errores"],
    ),
    "Cache de lecturas para un catalogo de alta demanda": (
        "INTERMEDIO",
        ["Caching", "Rendimiento", "Estructuras de datos"],
    ),
    "Pipeline ETL asincrono con validacion estricta": (
        "INTERMEDIO",
        ["ETL / CSV", "Validacion de datos", "Asyncio", "Manejo de errores"],
    ),
}

STARTER_GENERICO = '''"""Proyecto inicial del reto.

Implementa la funcion `procesar` respetando el contrato del enunciado.
Las pruebas oficiales viven fuera de este proyecto: tus propios tests no deciden la aprobacion.
"""


def procesar(entrada):
    # TODO: implementar segun el enunciado del reto
    raise NotImplementedError
'''

# --------------------------------------------------------------------------- reto ejecutable

STARTER_PAGOS = '''"""Registro idempotente de pagos.

Contrato:
    registrar_pagos(eventos: list[dict]) -> dict

Cada evento: {"id_idempotencia": str, "cuenta": str, "monto": float}

Devuelve:
    {
        "aplicados":  [ids en el orden en que se aplicaron],
        "duplicados": numero de reintentos identicos ignorados,
        "rechazados": [{"id": str | None, "motivo": str}],
    }

Motivos de rechazo: "DATOS_INVALIDOS" (monto <= 0, cuenta vacia o campos faltantes) y
"CONFLICTO_IDEMPOTENCIA" (mismo id con distinta cuenta o monto que el primero aplicado).
"""


def registrar_pagos(eventos):
    # TODO: implementar
    raise NotImplementedError
'''

_IMPORT = "import os, sys\nsys.path.insert(0, os.environ['PROYECTO_DIR'])\nfrom main import registrar_pagos\n\n"

PRUEBAS_PAGOS = [
    (
        "Aplica pagos validos en orden",
        CategoriaPrueba.FUNCIONAL,
        True,
        "Tres eventos validos con ids distintos se aplican en el orden recibido.",
        _IMPORT
        + "def test_aplica():\n"
        + "    r = registrar_pagos([{'id_idempotencia': 'a', 'cuenta': 'c1', 'monto': 10},"
        + " {'id_idempotencia': 'b', 'cuenta': 'c2', 'monto': 5.5}, {'id_idempotencia': 'c', 'cuenta': 'c1', 'monto': 1}])\n"
        + "    assert r['aplicados'] == ['a', 'b', 'c']\n    assert r['duplicados'] == 0\n    assert r['rechazados'] == []\n",
    ),
    (
        "Reintento identico no duplica el cobro",
        CategoriaPrueba.CASO_LIMITE,
        True,
        "Un evento repetido con el mismo id y payload se cuenta como duplicado y no se aplica dos veces.",
        _IMPORT
        + "def test_reintento():\n"
        + "    e = {'id_idempotencia': 'x', 'cuenta': 'c1', 'monto': 20}\n"
        + "    r = registrar_pagos([e, dict(e), dict(e)])\n"
        + "    assert r['aplicados'] == ['x']\n    assert r['duplicados'] == 2\n",
    ),
    (
        "Mismo id con distinto monto es conflicto",
        CategoriaPrueba.CASO_LIMITE,
        True,
        "Un id reutilizado con otro monto se rechaza con CONFLICTO_IDEMPOTENCIA y no altera el primero.",
        _IMPORT
        + "def test_conflicto():\n"
        + "    r = registrar_pagos([{'id_idempotencia': 'k', 'cuenta': 'c1', 'monto': 10},"
        + " {'id_idempotencia': 'k', 'cuenta': 'c1', 'monto': 99}])\n"
        + "    assert r['aplicados'] == ['k']\n"
        + "    assert r['rechazados'] == [{'id': 'k', 'motivo': 'CONFLICTO_IDEMPOTENCIA'}]\n",
    ),
    (
        "Datos invalidos se rechazan sin detener el lote",
        CategoriaPrueba.CASO_LIMITE,
        True,
        "Monto no positivo o cuenta vacia se rechazan con DATOS_INVALIDOS y el resto se procesa.",
        _IMPORT
        + "def test_invalidos():\n"
        + "    r = registrar_pagos([{'id_idempotencia': 'a', 'cuenta': '', 'monto': 3},"
        + " {'id_idempotencia': 'b', 'cuenta': 'c', 'monto': -1}, {'id_idempotencia': 'c', 'cuenta': 'c', 'monto': 2}])\n"
        + "    assert r['aplicados'] == ['c']\n"
        + "    assert [x['motivo'] for x in r['rechazados']] == ['DATOS_INVALIDOS', 'DATOS_INVALIDOS']\n",
    ),
    (
        "Cincuenta mil eventos en menos de dos segundos",
        CategoriaPrueba.RENDIMIENTO,
        False,
        "Procesa 50.000 eventos con 50% de reintentos en menos de 2 s.",
        _IMPORT
        + "import time\n\ndef test_volumen():\n"
        + "    ev = [{'id_idempotencia': str(i % 25000), 'cuenta': 'c', 'monto': 1} for i in range(50000)]\n"
        + "    t = time.perf_counter()\n    r = registrar_pagos(ev)\n"
        + "    assert time.perf_counter() - t < 2\n    assert len(r['aplicados']) == 25000\n",
    ),
]

NUEVOS = [
    {
        "organizacion": "Fintech Andina (demo)",
        "titulo": "Registro idempotente de pagos",
        "descripcion": (
            "Un servicio de pagos recibe reintentos de la red movil: el mismo evento puede llegar varias veces y, "
            "a veces, un cliente reutiliza el identificador con otro monto por error. Implementar registrar_pagos "
            "para que cada pago se aplique una sola vez, los reintentos identicos se cuenten como duplicados y los "
            "conflictos se rechacen sin afectar al pago original. Entorno de laboratorio: datos sinteticos."
        ),
        "criterios": "Superar las cuatro pruebas obligatorias. La de rendimiento es informativa.",
        "dificultad": "INTERMEDIO",
        "aptitudes": ["Idempotencia", "Estructuras de datos", "Validacion de datos", "Manejo de errores"],
        "proyecto": [
            {"ruta": "main.py", "contenido": STARTER_PAGOS},
            {
                "ruta": "README.md",
                "contenido": "Implementar registrar_pagos en main.py. Ver el contrato en su docstring.\n",
            },
        ],
        "pruebas": PRUEBAS_PAGOS,
    },
    {
        "organizacion": "Fintech Andina (demo)",
        "titulo": "Limitador de peticiones por cliente (Token Bucket)",
        "descripcion": (
            "Una API publica sufre rafagas de un mismo cliente que degradan al resto. Implementar un limitador "
            "Token Bucket por cliente con capacidad y tasa de recarga configurables, usando un reloj inyectable "
            "para que la logica se compruebe sin esperar tiempo real."
        ),
        "criterios": "Respetar capacidad y recarga exactas; aislar clientes entre si; no usar sleep.",
        "dificultad": "AVANZADO",
        "aptitudes": ["Rate limiting", "Concurrencia", "Diseno de APIs", "Testing con reloj simulado"],
        "proyecto": None,
        "pruebas": None,
    },
    {
        "organizacion": "Logistica Pacifico (demo)",
        "titulo": "Asignacion de rutas con cola de prioridad",
        "descripcion": (
            "Un centro de distribucion asigna pedidos urgentes y regulares a vehiculos disponibles. Implementar la "
            "asignacion con una cola de prioridad que respete urgencia, antiguedad y capacidad del vehiculo."
        ),
        "criterios": "Orden de asignacion exacto segun las reglas; ningun vehiculo excede su capacidad.",
        "dificultad": "INTERMEDIO",
        "aptitudes": ["Estructuras de datos", "Algoritmos", "Optimizacion"],
        "proyecto": None,
        "pruebas": None,
    },
    {
        "organizacion": "Logistica Pacifico (demo)",
        "titulo": "Normalizacion de direcciones para despacho",
        "descripcion": (
            "Las direcciones llegan con abreviaturas, tildes y formatos distintos. Normalizarlas a un formato unico "
            "y detectar duplicados probables antes de asignar despachos."
        ),
        "criterios": "Normalizacion determinista y deteccion de duplicados segun las reglas publicadas.",
        "dificultad": "BASICO",
        "aptitudes": ["Expresiones regulares", "Validacion de datos", "Limpieza de datos"],
        "proyecto": None,
        "pruebas": None,
    },
]

PRUEBAS_GENERICAS = [
    ("Contrato de la respuesta", CategoriaPrueba.FUNCIONAL, True, "La respuesta cumple el esquema acordado.", None),
    (
        "Casos limite del enunciado",
        CategoriaPrueba.CASO_LIMITE,
        True,
        "Entradas limite se tratan segun el contrato.",
        None,
    ),
    ("Entrada invalida", CategoriaPrueba.CASO_LIMITE, True, "La entrada invalida se rechaza sin efectos.", None),
    ("Tiempo bajo volumen", CategoriaPrueba.RENDIMIENTO, False, "Procesa el volumen de prueba bajo el limite.", None),
]

# --------------------------------------------------------------------------- perfiles demo

SOLUCION_BUENA = '''"""Registro idempotente de pagos."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pago:
    cuenta: str
    monto: float


def _validar(evento: dict) -> Pago | None:
    """Devuelve el pago normalizado o None si los datos no cumplen el contrato."""
    try:
        cuenta = str(evento["cuenta"]).strip()
        monto = float(evento["monto"])
    except (KeyError, TypeError, ValueError):
        return None
    if not cuenta or monto <= 0:
        return None
    return Pago(cuenta, monto)


def registrar_pagos(eventos: list[dict]) -> dict:
    """Aplica cada pago una sola vez; los reintentos identicos no duplican el cobro."""
    aplicados: dict[str, Pago] = {}
    orden: list[str] = []
    duplicados = 0
    rechazados: list[dict] = []

    for evento in eventos:
        clave = evento.get("id_idempotencia")
        pago = _validar(evento)
        if clave is None or pago is None:
            rechazados.append({"id": clave, "motivo": "DATOS_INVALIDOS"})
            continue
        previo = aplicados.get(clave)
        if previo is None:
            aplicados[clave] = pago
            orden.append(clave)
        elif previo == pago:
            duplicados += 1
        else:
            rechazados.append({"id": clave, "motivo": "CONFLICTO_IDEMPOTENCIA"})

    return {"aplicados": orden, "duplicados": duplicados, "rechazados": rechazados}
'''

TEST_PROPIO = """from main import registrar_pagos


def test_reintento_no_duplica():
    e = {"id_idempotencia": "a", "cuenta": "c", "monto": 1}
    assert registrar_pagos([e, e])["duplicados"] == 1
"""

SOLUCION_REGULAR = """def registrar_pagos(eventos):
    vistos = {}
    aplicados = []
    dup = 0
    rech = []
    for e in eventos:
        try:
            if e["monto"] <= 0 or e["cuenta"] == "":
                rech.append({"id": e.get("id_idempotencia"), "motivo": "DATOS_INVALIDOS"})
                continue
        except:
            rech.append({"id": None, "motivo": "DATOS_INVALIDOS"})
            continue
        k = e["id_idempotencia"]
        if k in vistos:
            if vistos[k] == (e["cuenta"], e["monto"]):
                dup += 1
            else:
                rech.append({"id": k, "motivo": "CONFLICTO_IDEMPOTENCIA"})
        else:
            vistos[k] = (e["cuenta"], e["monto"])
            aplicados.append(k)
    return {"aplicados": aplicados, "duplicados": dup, "rechazados": rech}
"""

SOLUCION_GENERICA = '''"""Solucion del reto."""

import logging

log = logging.getLogger(__name__)


def _normalizar(valor: str) -> str:
    return " ".join(valor.strip().split()).lower()


def procesar(entrada: list[dict]) -> dict:
    """Procesa la entrada segun el contrato del reto."""
    validos, rechazados = [], []
    for i, fila in enumerate(entrada, start=1):
        if not isinstance(fila, dict) or not fila:
            rechazados.append({"linea": i, "codigo": "ENTRADA_INVALIDA"})
            continue
        validos.append({k: _normalizar(str(v)) for k, v in fila.items()})
    log.info("procesadas %s filas", len(entrada))
    return {"validos": validos, "rechazados": rechazados}
'''

# nombre_publico, nombre, universidad, carrera, ciclo, [(titulo_reto, solucion, con_tests)]
DEMO = [
    (
        "valeria-quispe-demo",
        "Valeria Quispe",
        "UNI",
        "Ingenieria de Software",
        9,
        [
            ("Registro idempotente de pagos", SOLUCION_BUENA, True),
            ("Idempotencia y concurrencia en una pasarela de pagos", SOLUCION_BUENA, True),
            ("Pipeline ETL asincrono con validacion estricta", SOLUCION_GENERICA, False),
            ("Cache de lecturas para un catalogo de alta demanda", SOLUCION_GENERICA, False),
            ("Limitador de peticiones por cliente (Token Bucket)", SOLUCION_BUENA, True),
        ],
    ),
    (
        "diego-ramos-demo",
        "Diego Ramos",
        "UNMSM",
        "Ingenieria de Sistemas",
        8,
        [
            ("Registro idempotente de pagos", SOLUCION_BUENA, False),
            ("Pipeline ETL asincrono con validacion estricta", SOLUCION_GENERICA, False),
            ("Asignacion de rutas con cola de prioridad", SOLUCION_GENERICA, False),
        ],
    ),
    (
        "lucia-mendoza-demo",
        "Lucia Mendoza",
        "PUCP",
        "Ciencias de la Computacion",
        7,
        [
            ("Normalizacion de direcciones para despacho", SOLUCION_GENERICA, False),
            ("Registro idempotente de pagos", SOLUCION_REGULAR, False),
        ],
    ),
    (
        "jorge-huaman-demo",
        "Jorge Huaman",
        "UNI",
        "Ingenieria de Sistemas",
        6,
        [("Registro idempotente de pagos", SOLUCION_REGULAR, False)],
    ),
    (
        "sofia-torres-demo",
        "Sofia Torres",
        "UTEC",
        "Ciencia de Datos",
        7,
        [
            ("Pipeline ETL asincrono con validacion estricta", SOLUCION_GENERICA, True),
            ("Normalizacion de direcciones para despacho", SOLUCION_GENERICA, False),
        ],
    ),
]


def _proyecto(archivos: list[dict]) -> str:
    return documento_canonico(archivos)


def _organizacion(db, nombre: str) -> Organizacion:
    org = db.scalar(select(Organizacion).where(Organizacion.nombre == nombre))
    if org is None:
        org = Organizacion(nombre=nombre, descripcion="Organizacion ficticia de demostracion.")
        db.add(org)
        db.flush()
    return org


def ampliar(db) -> None:
    momento = ahora()
    tocados = 0

    for titulo, (dificultad, aptitudes) in ORIGINALES.items():
        reto = db.scalar(select(Reto).where(Reto.titulo == titulo))
        if reto is None:
            continue
        if reto.dificultad is None:
            reto.dificultad = dificultad
            reto.aptitudes = json.dumps(aptitudes, ensure_ascii=False)
            tocados += 1
        if reto.proyecto_base is None:
            reto.proyecto_base = _proyecto([{"ruta": "main.py", "contenido": STARTER_GENERICO}])

    nuevos = 0
    for datos in NUEVOS:
        if db.scalar(select(Reto).where(Reto.titulo == datos["titulo"])):
            continue
        org = _organizacion(db, datos["organizacion"])
        proyecto = datos["proyecto"] or [{"ruta": "main.py", "contenido": STARTER_GENERICO}]
        reto = Reto(
            organizacion_id=org.id,
            titulo=datos["titulo"],
            descripcion_publica=datos["descripcion"],
            criterios_aceptacion=datos["criterios"],
            estado=EstadoReto.PUBLICADO,
            momento_publicacion=momento,
            version_base="v1.0.0",
            dificultad=datos["dificultad"],
            aptitudes=json.dumps(datos["aptitudes"], ensure_ascii=False),
            proyecto_base=_proyecto(proyecto),
        )
        db.add(reto)
        db.flush()
        for i, (nombre, categoria, obligatoria, condicion, codigo) in enumerate(datos["pruebas"] or PRUEBAS_GENERICAS):
            db.add(
                Prueba(
                    reto_id=reto.id,
                    nombre=nombre,
                    categoria=categoria,
                    obligatoria=obligatoria,
                    condicion_aprobacion=condicion,
                    referencia_ejecutable=f"tests/test_{i + 1}.py",
                    limite_ejecucion_ms=5000 if categoria == CategoriaPrueba.RENDIMIENTO else None,
                    contenido_ejecutable=codigo,
                )
            )
        nuevos += 1
    db.commit()

    perfiles = 0
    sin_modelo = ClienteLLM("", "http://sin-modelo", "ninguno")  # el juez de la siembra es solo estatico
    for nombre_publico, nombre, uni, carrera, ciclo, entregas in DEMO:
        if db.scalar(select(PerfilEstudiante).where(PerfilEstudiante.nombre_publico == nombre_publico)):
            continue
        usuario = Usuario(nombre=nombre, correo=f"{nombre_publico}@demo.qo", hash_password=hash_password(CLAVE_DEMO))
        db.add(usuario)
        db.flush()
        db.add(
            PerfilEstudiante(
                usuario_id=usuario.id,
                nombre_publico=nombre_publico,
                biografia="Perfil de demostracion: sus credenciales provienen de la siembra de datos (seed-demo:v1).",
                visibilidad=VisibilidadPerfil.PUBLICO,
                universidad=uni,
                carrera=carrera,
                ciclo=ciclo,
            )
        )
        db.flush()
        for titulo, solucion, con_tests in entregas:
            reto = db.scalar(select(Reto).where(Reto.titulo == titulo))
            if reto is None:
                continue
            archivos = [{"ruta": "main.py", "contenido": solucion}]
            if con_tests:
                archivos.append({"ruta": "tests/test_propio.py", "contenido": TEST_PROPIO})
            documento = _proyecto(archivos)
            participacion = Participacion(perfil_usuario_id=usuario.id, reto_id=reto.id)
            db.add(participacion)
            db.flush()
            entrega = Entrega(
                participacion_id=participacion.id,
                numero_intento=1,
                repositorio="editor-web",
                commit=huella(documento)[:12],
                proyecto=documento,
                huella_proyecto=huella(documento),
            )
            db.add(entrega)
            db.flush()
            evaluacion = Evaluacion(
                entrega_id=entrega.id,
                estado_procesamiento=EstadoEvaluacion.FINALIZADA,
                momento_inicio=momento,
                momento_fin=momento,
                version_evaluador="seed-demo:v1",
                dictamen=Dictamen.APROBADO,
            )
            db.add(evaluacion)
            db.flush()
            for prueba in reto.pruebas:
                db.add(
                    ResultadoPrueba(
                        evaluacion_id=evaluacion.id,
                        prueba_id=prueba.id,
                        condicion_ejecucion=CondicionEjecucion.EJECUTADA,
                        aprobada=True,
                        detalle="Resultado de siembra de demostracion, no de una ejecucion.",
                    )
                )
            db.flush()
            db.refresh(evaluacion)
            juez_ia.revisar(db, evaluacion, cliente=sin_modelo)
            certificacion.emitir(db, evaluacion)
        perfiles += 1
    db.commit()

    print(
        f"Ampliacion IA: {tocados} retos originales completados, {nuevos} retos nuevos, "
        f"{perfiles} perfiles de demostracion para el ranking."
    )
