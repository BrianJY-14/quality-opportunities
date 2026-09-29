"""Funciones de IA: AI Scoper, Juez IA, tutor, defensa tecnica, CV dinamico y ranking.

Ninguna prueba sale a la red: el cliente LLM se sustituye por un doble que responde segun las
instrucciones de sistema que recibe y anota todo lo que se le envia. Asi se comprueba tambien lo
que NO debe salir de la plataforma (secretos del issue original).

| Prueba                              | Resultado que comprueba                                                   |
| Analisis estatico                   | Linea exacta del error de sintaxis y las cuatro reglas del componente A  |
| Scoper sanea antes de enviar        | Ningun secreto del issue llega al proveedor                              |
| Scoper valida el contrato           | Rendimiento nunca obligatorio; minimo dos obligatorias                   |
| Scoper con proveedor caido          | Cae al preparador por reglas y lo dice                                   |
| Solicitud de extremo a extremo      | El borrador guarda codigo de pruebas y proyecto base, sin exponerlos     |
| Proyecto base                       | El editor nace con el starter del reto                                   |
| Entrega congelada                   | Editar despues de enviar no cambia la huella de lo entregado             |
| Juez IA                             | Con modelo: COMPLETADA; sin modelo: SOLO_ESTATICA; nunca cambia dictamen |
| Tutor                               | Diagnostica la sintaxis, no devuelve codigo y limita la frecuencia       |
| Defensa                             | Preguntas sin rubrica, calificacion, tope a respuestas cortas, 422       |
| CV y ranking                        | Grafo con evidencia, rango por XP y ranking ordenado                     |
"""

import json

import pytest

from app.servicios import analisis_estatico, llm, tutor_ia
from app.servicios.preparador_llm import PreparadorLLM
from tests.conftest import auth, commit_que_aprueba, reto_fresco


class LLMDoble:
    disponible = True
    etiqueta = "doble:modelo-prueba"

    def __init__(self, fallar: bool = False):
        self.fallar = fallar
        self.enviado: list[str] = []

    def json(self, sistema: str, usuario: str, **_):
        self.enviado.append(usuario)
        if self.fallar:
            raise llm.FalloLLM("caido")
        if "AI Pedagogical Scoper" in sistema:
            return {
                "titulo": "Deduplicar eventos de pago",
                "descripcion_publica": "Evitar cobros duplicados. Contacto: ops@empresa.pe",
                "criterios_aceptacion": "Cada pago se aplica una vez.",
                "dificultad": "intermedio",
                "aptitudes": ["Idempotencia", "Validacion de datos"],
                "proyecto_base": [
                    {"ruta": "main.py", "contenido": "def procesar(e):\n    raise NotImplementedError\n"},
                    {"ruta": "../fuera.py", "contenido": "x"},
                ],
                "pruebas": [
                    {
                        "nombre": "Funcional",
                        "categoria": "FUNCIONAL",
                        "obligatoria": True,
                        "condicion_aprobacion": "ok",
                        "referencia_ejecutable": "tests/test_a.py",
                        "codigo_pytest": "def test_a():\n    assert True\n",
                    },
                    {
                        "nombre": "Borde",
                        "categoria": "CASO_LIMITE",
                        "obligatoria": False,
                        "condicion_aprobacion": "ok",
                        "referencia_ejecutable": "../../etc/passwd",
                    },
                    {"nombre": "Carga", "categoria": "RENDIMIENTO", "obligatoria": True, "condicion_aprobacion": "p95"},
                    {"nombre": "Otra", "categoria": "INVENTADA", "obligatoria": False, "condicion_aprobacion": "ok"},
                ],
                "resumen_preparacion": "Adaptado.",
            }
        if "Juez IA" in sistema:
            return {
                "dimensiones": {"arquitectura": 82, "legibilidad": 75, "robustez": 140, "pruebas": 40, "seguridad": 90},
                "aptitudes": [{"nombre": "Idempotencia", "evidencia": "main.py usa un diccionario por clave"}],
                "fortalezas": ["Funciones cortas"],
                "mejoras": ["Agregar pruebas propias"],
                "resumen": "Solucion solida.",
            }
        if "Tutor IA" in sistema:
            return {
                "diagnosticos": [
                    {
                        "archivo": "main.py",
                        "linea": 2,
                        "severidad": "error",
                        "mensaje": "Falta algo",
                        "pista": "```python\nreturn 42\n```",
                    }
                ],
                "respuesta": "Piensa en el caso vacio. ```def solucion(): pass```",
                "siguiente_paso": "Revisa la linea 2",
                "conceptos": ["Sintaxis"],
            }
        if "entrevistador tecnico" in sistema:
            return {
                "preguntas": [
                    {
                        "id": "x",
                        "pregunta": "Por que suma usa +?",
                        "enfoque": "DISENO",
                        "archivo": "main.py",
                        "puntos_clave": ["aritmetica"],
                    },
                    {
                        "id": "y",
                        "pregunta": "Que pasa con None?",
                        "enfoque": "CASO_LIMITE",
                        "archivo": "main.py",
                        "puntos_clave": ["TypeError"],
                    },
                    {
                        "id": "z",
                        "pregunta": "Y con millones?",
                        "enfoque": "ADAPTACION",
                        "archivo": "main.py",
                        "puntos_clave": ["O(1)"],
                    },
                ]
            }
        if "evaluador de la defensa" in sistema:
            return {
                "calificaciones": [
                    {"id": "p1", "puntaje": 90, "comentario": "Bien"},
                    {"id": "p2", "puntaje": 80, "comentario": "Bien"},
                    {"id": "p3", "puntaje": 95, "comentario": "Bien"},
                ],
                "retroalimentacion": "Reforzar casos limite.",
            }
        if "resumen profesional" in sistema:
            return {"resumen": "Perfil con evidencia verificada en retos de pagos."}
        raise AssertionError(f"instruccion no esperada: {sistema[:60]}")


class SinModelo:
    disponible = False
    etiqueta = "ninguno"

    def json(self, *a, **k):
        raise llm.FalloLLM("sin clave")


@pytest.fixture
def doble():
    d = LLMDoble()
    llm.establecer_cliente(d)
    tutor_ia._ventanas.clear()
    yield d
    llm.establecer_cliente(None)


@pytest.fixture
def sin_modelo():
    llm.establecer_cliente(SinModelo())
    tutor_ia._ventanas.clear()
    yield
    llm.establecer_cliente(None)


def _participar(cliente, token, titulo):
    reto_id = reto_fresco(cliente, titulo)
    return reto_id, cliente.post(f"/api/v1/retos/{reto_id}/participaciones", headers=auth(token)).json()["id"]


def _guardar(cliente, token, pid, archivos):
    rev = cliente.get(f"/api/v1/participaciones/{pid}/workspace", headers=auth(token)).json()["revision"]
    r = cliente.put(
        f"/api/v1/participaciones/{pid}/workspace",
        headers=auth(token),
        json={"revision_base": rev, "archivos": archivos},
    )
    assert r.status_code == 200, r.text


CODIGO = [{"ruta": "main.py", "contenido": 'def suma(a: int, b: int) -> int:\n    """Suma."""\n    return a + b\n'}]


# ------------------------------------------------------------------ analisis estatico


def test_analisis_estatico_ubica_el_error_y_evalua_las_reglas():
    res = analisis_estatico.analizar(
        [
            {
                "ruta": "main.py",
                "contenido": "import pickle\nfrom os import *\ntry:\n    eval('1')\nexcept:\n    pass\n",
            },
            {"ruta": "roto.py", "contenido": "def f(:\n    pass\n"},
        ]
    )
    assert not res.compila
    error = next(d for d in res.diagnosticos if d.origen == "COMPILACION_PYTHON")
    assert (error.archivo, error.linea) == ("roto.py", 1)
    assert res.reglas == {k: False for k in analisis_estatico.REGLAS}
    assert res.puntaje_reglas == 0


# ------------------------------------------------------------------ AI Scoper


def test_scoper_sanea_antes_de_enviar_y_valida_el_contrato():
    d = LLMDoble()
    borrador = PreparadorLLM(cliente=d).proponer(
        "Pagos duplicados", "api_key=sk-SECRETO en 10.0.0.12, escribir a jefe@banco.pe"
    )
    enviado = d.enviado[0]
    assert "sk-SECRETO" not in enviado and "10.0.0.12" not in enviado and "jefe@banco.pe" not in enviado
    # La salida tambien se sanea: el correo que el modelo invento no llega al borrador.
    assert "ops@empresa.pe" not in borrador.descripcion_publica

    assert borrador.modelo == "doble:modelo-prueba"
    assert borrador.dificultad == "INTERMEDIO"
    por_nombre = {p.nombre: p for p in borrador.pruebas}
    assert por_nombre["Carga"].obligatoria is False  # rendimiento nunca obligatorio
    assert sum(p.obligatoria for p in borrador.pruebas) >= 2  # se promovio una para cumplir el minimo
    assert ".." not in por_nombre["Borde"].referencia_ejecutable
    assert por_nombre["Funcional"].contenido_ejecutable.startswith("def test_a")
    assert [a["ruta"] for a in borrador.proyecto_base] == ["main.py"]  # la ruta con .. se descarto


def test_scoper_con_proveedor_caido_usa_el_respaldo():
    borrador = PreparadorLLM(cliente=LLMDoble(fallar=True)).proponer("Titulo", "contenido")
    assert borrador.modelo == "reglas:v1"
    assert "no respondio" in borrador.resumen_preparacion


def test_solicitud_con_llm_deja_un_borrador_revisable(cliente, representante, doble, monkeypatch):
    from app.servicios import registro

    monkeypatch.setattr(registro.settings, "PREPARADOR", "llm")
    org_id = representante["usuario"]["representaciones"][0]["organizacion_id"]
    r = cliente.post(
        "/api/v1/solicitudes",
        headers=auth(representante["token"]),
        json={"organizacion_id": org_id, "titulo_original": "Cobros duplicados", "contenido_original": "token=abc123"},
    )
    assert r.status_code == 202, r.text
    solicitud = cliente.get(f"/api/v1/solicitudes/{r.json()['id']}", headers=auth(representante["token"])).json()
    assert solicitud["estado_preparacion"] == "LISTA"
    assert solicitud["modelo_ia"] == "doble:modelo-prueba"

    reto_id = solicitud["reto_borrador_id"]
    borrador = cliente.get(f"/api/v1/retos/{reto_id}/borrador", headers=auth(representante["token"])).json()
    assert borrador["aptitudes"] == ["Idempotencia", "Validacion de datos"]
    assert borrador["proyecto_base"][0]["ruta"] == "main.py"
    assert any(p["contenido_ejecutable"] for p in borrador["pruebas"])

    portal = cliente.get(f"/api/v1/organizaciones/{org_id}/retos", headers=auth(representante["token"])).json()
    assert any(x["id"] == reto_id and x["estado"] == "BORRADOR" for x in portal)

    # Publicado, el detalle publico dice que hay codigo pero no lo muestra.
    cliente.post(f"/api/v1/retos/{reto_id}/publicacion", headers=auth(representante["token"]))
    publico = cliente.get(f"/api/v1/retos/{reto_id}").json()
    assert any(p["tiene_codigo"] for p in publico["pruebas"])
    assert "contenido_ejecutable" not in json.dumps(publico)


# ------------------------------------------------------------------ editor y entrega


def test_el_editor_nace_con_el_proyecto_base_del_reto(cliente, estudiante, datos_demo):
    token = estudiante()
    retos = cliente.get("/api/v1/retos", params={"q": "Registro idempotente"}).json()["items"]
    pid = cliente.post(f"/api/v1/retos/{retos[0]['id']}/participaciones", headers=auth(token)).json()["id"]
    espacio = cliente.get(f"/api/v1/participaciones/{pid}/workspace", headers=auth(token)).json()
    assert espacio["revision"] == 0
    assert "registrar_pagos" in next(a["contenido"] for a in espacio["archivos"] if a["ruta"] == "main.py")


def test_la_entrega_congela_el_proyecto(cliente, estudiante, sin_modelo):
    token = estudiante()
    _, pid = _participar(cliente, token, "Congelar")
    _guardar(cliente, token, pid, CODIGO)
    r = cliente.post(
        f"/api/v1/participaciones/{pid}/entregas",
        headers=auth(token),
        json={"repositorio": "editor", "commit": "abcdef1"},
    )
    assert r.status_code == 202
    _guardar(cliente, token, pid, [{"ruta": "main.py", "contenido": "cambiado = 1\n"}])
    entrega = cliente.get(f"/api/v1/participaciones/{pid}/entregas", headers=auth(token)).json()[0]
    from app.servicios.workspace import documento_canonico, huella

    assert entrega["huella_proyecto"] == huella(documento_canonico(CODIGO))


# ------------------------------------------------------------------ juez IA


def test_juez_ia_con_modelo_completa_la_revision_sin_tocar_el_dictamen(cliente, estudiante, doble):
    token = estudiante()
    _, pid = _participar(cliente, token, "Juez con modelo")
    _guardar(cliente, token, pid, CODIGO)
    commit_que_aprueba(cliente, token, pid)
    entrega = cliente.get(f"/api/v1/participaciones/{pid}/entregas", headers=auth(token)).json()[0]
    ev = cliente.get(f"/api/v1/evaluaciones/{entrega['evaluaciones'][0]}", headers=auth(token)).json()
    assert ev["dictamen"] == "APROBADO"
    rev = ev["revision_ia"]
    assert rev["estado"] == "COMPLETADA" and rev["modelo"] == "doble:modelo-prueba"
    assert rev["dimensiones"]["robustez"] == 100  # acotado a 0..100
    assert rev["analisis_estatico"]["puntaje_reglas"] == 100
    assert 0 <= rev["puntaje_global"] <= 100


def test_juez_ia_sin_modelo_deja_revision_estatica(cliente, estudiante, sin_modelo):
    token = estudiante()
    _, pid = _participar(cliente, token, "Juez sin modelo")
    _guardar(cliente, token, pid, CODIGO)
    r = cliente.post(
        f"/api/v1/participaciones/{pid}/entregas",
        headers=auth(token),
        json={"repositorio": "editor", "commit": "abc1234"},
    )
    from tests.conftest import esperar

    ev = esperar(cliente, token, r.json()["evaluacion_id"])
    assert ev["revision_ia"]["estado"] == "SOLO_ESTATICA"
    assert ev["revision_ia"]["modelo"] == "estatico:v1"


# ------------------------------------------------------------------ tutor


def test_tutor_diagnostica_sin_dar_codigo_y_limita_la_frecuencia(cliente, estudiante, doble):
    token = estudiante()
    _, pid = _participar(cliente, token, "Tutor")
    _guardar(cliente, token, pid, [{"ruta": "main.py", "contenido": "def f(:\n    pass\n"}])

    r = cliente.post(f"/api/v1/participaciones/{pid}/tutor", headers=auth(token), json={"pregunta": "Que falla?"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["modo"] == "IA" and cuerpo["revision"] == 1
    assert any(d["origen"] == "COMPILACION_PYTHON" and d["linea"] == 1 for d in cuerpo["diagnosticos"])
    assert "```" not in json.dumps(cuerpo)  # el tutor no entrega soluciones

    for _ in range(tutor_ia.LIMITE_POR_MINUTO - 1):
        cliente.post(f"/api/v1/participaciones/{pid}/tutor", headers=auth(token), json={})
    assert cliente.post(f"/api/v1/participaciones/{pid}/tutor", headers=auth(token), json={}).status_code == 429


def test_tutor_de_otra_persona_es_404(cliente, estudiante, doble):
    _, pid = _participar(cliente, estudiante(), "Tutor ajeno")
    assert cliente.post(f"/api/v1/participaciones/{pid}/tutor", headers=auth(estudiante()), json={}).status_code == 404


# ------------------------------------------------------------------ defensa


def _entrega_con_codigo(cliente, token, titulo):
    _, pid = _participar(cliente, token, titulo)
    _guardar(cliente, token, pid, CODIGO)
    r = cliente.post(
        f"/api/v1/participaciones/{pid}/entregas",
        headers=auth(token),
        json={"repositorio": "editor", "commit": "abc9999"},
    )
    return r.json()["entrega_id"]


RESPUESTA_LARGA = "La funcion suma recibe dos enteros tipados y devuelve su suma con el operador mas, sin efectos."


def test_defensa_genera_preguntas_y_califica(cliente, estudiante, doble):
    token = estudiante()
    entrega_id = _entrega_con_codigo(cliente, token, "Defensa")

    d = cliente.post(f"/api/v1/entregas/{entrega_id}/defensas", headers=auth(token)).json()
    assert [p["id"] for p in d["preguntas"]] == ["p1", "p2", "p3"]
    assert "puntos_clave" not in json.dumps(d)  # la rubrica es privada
    # Repetir devuelve la misma defensa pendiente.
    assert cliente.post(f"/api/v1/entregas/{entrega_id}/defensas", headers=auth(token)).json()["id"] == d["id"]

    incompleta = cliente.post(
        f"/api/v1/defensas/{d['id']}/respuestas",
        headers=auth(token),
        json={"respuestas": [{"pregunta_id": "p1", "respuesta": RESPUESTA_LARGA}]},
    )
    assert incompleta.status_code == 422

    respuestas = [
        {"pregunta_id": "p1", "respuesta": RESPUESTA_LARGA},
        {"pregunta_id": "p2", "respuesta": RESPUESTA_LARGA},
        {"pregunta_id": "p3", "respuesta": "No lo se, pero lo pensare."},
    ]
    r = cliente.post(f"/api/v1/defensas/{d['id']}/respuestas", headers=auth(token), json={"respuestas": respuestas})
    assert r.status_code == 200, r.text
    final = r.json()
    assert final["estado"] == "CALIFICADA"
    assert final["calificaciones"]["p3"]["puntaje"] == 20  # respuesta corta: tope, diga lo que diga el modelo
    assert final["puntaje"] == round((90 + 80 + 20) / 3)
    assert final["aprobada"] is True


def test_defensa_sin_modelo_no_inventa_calificacion(cliente, estudiante, sin_modelo):
    token = estudiante()
    entrega_id = _entrega_con_codigo(cliente, token, "Defensa sin modelo")
    d = cliente.post(f"/api/v1/entregas/{entrega_id}/defensas", headers=auth(token)).json()
    assert d["modelo"] == "plantilla:v1"
    r = cliente.post(
        f"/api/v1/defensas/{d['id']}/respuestas",
        headers=auth(token),
        json={"respuestas": [{"pregunta_id": p["id"], "respuesta": RESPUESTA_LARGA} for p in d["preguntas"]]},
    ).json()
    assert r["estado"] == "SIN_CALIFICAR" and r["puntaje"] is None


# ------------------------------------------------------------------ CV y ranking


def test_cv_y_ranking_se_derivan_de_la_evidencia(cliente, estudiante, doble):
    token = estudiante()
    nombre = cliente.get("/api/v1/auth/yo/perfil", headers=auth(token)).json()["nombre_publico"]
    _, pid = _participar(cliente, token, "CV")
    _guardar(cliente, token, pid, CODIGO)
    commit_que_aprueba(cliente, token, pid)

    cv = cliente.get(f"/api/v1/perfiles/{nombre}/cv").json()
    assert cv["metricas"]["credenciales_vigentes"] == 1
    assert cv["rango"]["codigo"] == "CACHIMBO" and cv["rango"]["xp"] > 0
    idem = next(a for a in cv["aptitudes"] if a["nombre"] == "Idempotencia")
    assert idem["evidencias"][0]["reto"] == "CV"
    assert any(n["tipo"] == "EVIDENCIA" for n in cv["grafo"]["nodos"])

    resumen = cliente.post("/api/v1/auth/yo/cv/resumen", headers=auth(token)).json()
    assert resumen["resumen_ia"].startswith("Perfil con evidencia")

    ranking = cliente.get("/api/v1/ranking").json()
    xp = [f["xp"] for f in ranking["filas"]]
    assert xp == sorted(xp, reverse=True)
    assert ranking["filas"][0]["nombre_publico"] == "valeria-quispe-demo"
    assert any(f["nombre_publico"] == nombre for f in ranking["filas"])
    assert [r["codigo"] for r in ranking["rangos"]][-1] == "ORACULO_TECH"


def test_resumen_sin_modelo_responde_503(cliente, estudiante, sin_modelo):
    assert cliente.post("/api/v1/auth/yo/cv/resumen", headers=auth(estudiante())).status_code == 503


# ------------------------------------------------------------------ cliente HTTP


def test_cliente_llm_arma_la_peticion_y_reintenta_un_429(monkeypatch):
    import httpx

    llamadas = []

    def falso_post(url, json, headers, timeout):
        llamadas.append((url, json, headers))
        if len(llamadas) == 1:
            return httpx.Response(429, text="rate limit")
        return httpx.Response(200, json={"choices": [{"message": {"content": '```json\n{"ok": true}\n```'}}]})

    monkeypatch.setattr(httpx, "post", falso_post)
    monkeypatch.setattr("time.sleep", lambda _: None)
    c = llm.ClienteLLM("gsk_clave", "https://api.groq.com/openai/v1/", "llama-3.3-70b-versatile")
    assert c.json("sistema JSON", "usuario") == {"ok": True}
    url, cuerpo, cabeceras = llamadas[-1]
    assert url == "https://api.groq.com/openai/v1/chat/completions"
    assert cuerpo["response_format"] == {"type": "json_object"}
    assert cabeceras["Authorization"] == "Bearer gsk_clave"
    assert c.etiqueta == "groq.com:llama-3.3-70b-versatile"


def test_cliente_llm_reintenta_sin_modo_json_si_groq_lo_rechaza(monkeypatch):
    import httpx

    cuerpos = []

    def falso_post(url, json, headers, timeout):
        cuerpos.append(dict(json))
        if len(cuerpos) == 1:
            return httpx.Response(400, text='{"error":{"code":"json_validate_failed"}}')
        return httpx.Response(200, json={"choices": [{"message": {"content": 'Aqui va: {"ok": true}'}}]})

    monkeypatch.setattr(httpx, "post", falso_post)
    c = llm.ClienteLLM("gsk_clave", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile")
    assert c.json("sistema JSON", "usuario") == {"ok": True}
    assert "response_format" in cuerpos[0] and "response_format" not in cuerpos[1]


def test_juez_ia_guarda_el_motivo_y_se_puede_reintentar(cliente, estudiante):
    caido = LLMDoble(fallar=True)
    llm.establecer_cliente(caido)
    try:
        token = estudiante()
        _, pid = _participar(cliente, token, "Juez que se reintenta")
        _guardar(cliente, token, pid, CODIGO)
        commit_que_aprueba(cliente, token, pid)
        entrega = cliente.get(f"/api/v1/participaciones/{pid}/entregas", headers=auth(token)).json()[0]
        ev_id = entrega["evaluaciones"][0]
        rev = cliente.get(f"/api/v1/evaluaciones/{ev_id}/revision-ia", headers=auth(token)).json()
        assert rev["estado"] == "SOLO_ESTATICA" and "caido" in rev["resumen"]

        llm.establecer_cliente(LLMDoble())
        r = cliente.post(f"/api/v1/evaluaciones/{ev_id}/revision-ia", headers=auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["estado"] == "COMPLETADA"
        # Una revision completada no se rehace.
        llm.establecer_cliente(caido)
        again = cliente.post(f"/api/v1/evaluaciones/{ev_id}/revision-ia", headers=auth(token)).json()
        assert again["estado"] == "COMPLETADA"
    finally:
        llm.establecer_cliente(None)


def test_dictamen_distingue_no_ejecutada_de_no_cumplida():
    from types import SimpleNamespace as N

    from app.dominio.enums import CondicionEjecucion as C
    from app.servicios.evaluacion import _dictaminar

    p1, p2 = N(id=1, obligatoria=True), N(id=2, obligatoria=False)
    ok = lambda i: N(prueba_id=i, condicion_ejecucion=C.EJECUTADA, aprobada=True)  # noqa: E731
    mal = lambda i: N(prueba_id=i, condicion_ejecucion=C.EJECUTADA, aprobada=False)  # noqa: E731
    sin = lambda i: N(prueba_id=i, condicion_ejecucion=C.NO_EJECUTADA, aprobada=None)  # noqa: E731

    assert _dictaminar([p1, p2], [sin(1), sin(2)]) == "NO_EVALUABLE"
    assert _dictaminar([p1, p2], [ok(1), sin(2)]) == "NO_EVALUABLE"
    assert _dictaminar([p1, p2], [mal(1), sin(2)]) == "NO_APROBADO"
    assert _dictaminar([p1, p2], [ok(1), mal(2)]) == "APROBADO"
    assert _dictaminar([p1, p2], [ok(1), ok(2)]) == "APROBADO"
    assert _dictaminar([p1], []) == "NO_EVALUABLE"
