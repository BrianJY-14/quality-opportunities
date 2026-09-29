"""Regresion del fallo del hackaton: evaluaciones colgadas en EN_EJECUCION.

| Prueba                          | Resultado que comprueba                                             |
| Evaluador que no responde       | Al vencer el limite la evaluacion cierra en ERROR_TECNICO           |
| Fallo fuera del evaluador       | Una excepcion al persistir tambien cierra en ERROR_TECNICO          |
| Proceso reiniciado              | Una evaluacion huerfana se cierra al consultarla                    |
| Credencial corregida a mano     | criterios como lista y claves faltantes no producen un 500          |
"""

import json
import threading
import uuid
from datetime import timedelta

from app.models import Credencial, Evaluacion
from app.models._base import ahora
from app.servicios import evaluacion as servicio
from tests.conftest import auth, commit_que_aprueba, esperar, reto_fresco


def _participar(cliente, token, titulo):
    reto_id = reto_fresco(cliente, titulo)
    return cliente.post(f"/api/v1/retos/{reto_id}/participaciones", headers=auth(token)).json()["id"]


def _entregar(cliente, token, pid):
    return cliente.post(
        f"/api/v1/participaciones/{pid}/entregas",
        headers=auth(token),
        json={"repositorio": "editor", "commit": "abc1234"},
    ).json()["evaluacion_id"]


def test_evaluador_que_no_responde_cierra_en_error_tecnico(cliente, estudiante, monkeypatch):
    liberar = threading.Event()

    class Colgado:
        def ejecutar(self, *a, **k):
            liberar.wait(5)  # simula un sandbox esperando su imagen
            raise RuntimeError("no deberia llegar a usarse")

    monkeypatch.setattr(servicio, "obtener_evaluador", lambda: Colgado())
    monkeypatch.setattr(servicio.get_settings(), "LIMITE_EVALUACION_S", 1)
    token = estudiante()
    ev = esperar(cliente, token, _entregar(cliente, token, _participar(cliente, token, "Colgado")))
    liberar.set()
    assert ev["estado_procesamiento"] == "ERROR_TECNICO"
    assert "no respondio en 1 s" in ev["detalle_error"]
    assert ev["dictamen"] is None


def test_fallo_fuera_del_evaluador_tambien_cierra(cliente, estudiante, monkeypatch):
    def explota(*a, **k):
        raise RuntimeError("fallo al persistir")

    monkeypatch.setattr(servicio, "_dictaminar", explota)
    token = estudiante()
    ev = esperar(cliente, token, _entregar(cliente, token, _participar(cliente, token, "Explota")))
    assert ev["estado_procesamiento"] == "ERROR_TECNICO"


def test_evaluacion_huerfana_se_cierra_al_consultarla(cliente, estudiante, monkeypatch):
    # El proceso "muere": la tarea en segundo plano nunca corre.
    monkeypatch.setattr(servicio, "procesar", lambda _id: None)
    token = estudiante()
    ev_id = _entregar(cliente, token, _participar(cliente, token, "Huerfana"))
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        ev = db.get(Evaluacion, uuid.UUID(ev_id))
        ev.momento_solicitud = ahora() - timedelta(hours=1)
        db.commit()
    cuerpo = cliente.get(f"/api/v1/evaluaciones/{ev_id}", headers=auth(token)).json()
    assert cuerpo["estado_procesamiento"] == "ERROR_TECNICO"
    assert "interrumpio" in cuerpo["detalle_error"]


def test_credencial_con_criterios_en_lista_no_rompe(cliente, estudiante):
    token = estudiante()
    pid = _participar(cliente, token, "Credencial parcheada")
    commit_que_aprueba(cliente, token, pid)
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        cred = db.query(Credencial).order_by(Credencial.momento_emision.desc()).first()
        contenido = json.loads(cred.contenido_emitido)
        contenido["criterios_aceptacion"] = ["Superar las obligatorias.", "Sin regresiones."]
        del contenido["repositorio"]
        cred.contenido_emitido = json.dumps(contenido)
        db.commit()
        ident = cred.identificador_publico
    r = cliente.get(f"/api/v1/credenciales/{ident}")
    assert r.status_code == 200, r.text
    assert r.json()["criterios_aceptacion"] == "Superar las obligatorias.\nSin regresiones."
