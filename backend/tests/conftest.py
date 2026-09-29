import os
import pathlib

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "clave-de-prueba")
# La suite corre SIEMPRE con el evaluador simulado, aunque el .env local tenga EVALUADOR=e2b:
# una prueba automatica no debe crear sandboxes remotos, gastar creditos ni depender de la red.
# Una variable del entorno gana sobre el .env, asi que basta con fijarla aqui.
os.environ["EVALUADOR"] = "simulado"
# Lo mismo con el modelo de lenguaje: aunque el .env local tenga LLM_API_KEY, la suite no llama al
# proveedor. Las pruebas de IA inyectan un doble con `llm.establecer_cliente`.
os.environ["LLM_API_KEY"] = ""
os.environ["PREPARADOR"] = "reglas"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

CLAVE = "clave-de-prueba"


@pytest.fixture(scope="session", autouse=True)
def esquema():
    """Las pruebas corren sobre el esquema que produce Alembic, no sobre `create_all`."""
    raiz = pathlib.Path(__file__).resolve().parents[1]
    cfg = Config(str(raiz / "alembic.ini"))
    cfg.set_main_option("script_location", str(raiz / "alembic"))

    # `drop_all` borra las tablas del modelo, pero `alembic_version` no pertenece al modelo y
    # sobrevive. Si se queda apuntando a head, la corrida siguiente encuentra la base "al dia",
    # no aplica ninguna migracion y todas las pruebas fallan con "no such table".
    _vaciar(engine)
    command.upgrade(cfg, "head")
    yield
    _vaciar(engine)


def _vaciar(motor) -> None:
    Base.metadata.drop_all(bind=motor)
    with motor.begin() as conexion:
        conexion.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def datos_demo(esquema):
    import seed

    seed.main()


@pytest.fixture
def reto(cliente, datos_demo) -> dict:
    return cliente.get("/api/v1/retos").json()["items"][0]


@pytest.fixture
def representante(cliente, datos_demo) -> dict:
    """Usuario con representacion GESTOR_Y_REVOCADOR sobre la organizacion sembrada."""
    r = cliente.post("/api/v1/auth/login", json={"correo": "representante@ejemplo.pe", "password": "demo12345"}).json()
    return {"token": r["access_token"], "usuario": r["usuario"]}


@pytest.fixture
def estudiante(cliente):
    """Fabrica de estudiantes: cada prueba trabaja con el suyo, sin acoplarse a las demas."""
    import uuid

    def crear(con_perfil: bool = True) -> str:
        correo = f"est-{uuid.uuid4().hex[:8]}@uni.pe"
        cuerpo = {"correo": correo, "password": CLAVE, "nombre": "Estudiante Prueba"}
        if con_perfil:
            cuerpo["perfil_estudiante"] = {
                "nombre_publico": f"perfil-{uuid.uuid4().hex[:8]}",
                "universidad": "UNI",
                "carrera": "Ingenieria de Sistemas",
                "ciclo": 7,
            }
        cliente.post("/api/v1/auth/registro", json=cuerpo)
        return cliente.post("/api/v1/auth/login", json={"correo": correo, "password": CLAVE}).json()["access_token"]

    return crear


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def esperar(cliente, token: str, evaluacion_id: str, intentos: int = 60) -> dict:
    """Sustituye al polling del frontend."""
    import time

    for _ in range(intentos):
        cuerpo = cliente.get(f"/api/v1/evaluaciones/{evaluacion_id}", headers=auth(token)).json()
        if cuerpo["estado_procesamiento"] not in ("PENDIENTE", "EN_EJECUCION"):
            return cuerpo
        time.sleep(0.05)
    raise AssertionError("la evaluacion no termino a tiempo")


def commit_que_aprueba(cliente, token: str, participacion_id: str) -> str:
    """Busca un commit cuya evaluacion apruebe. El evaluador es determinista, asi que el
    commit encontrado aprueba siempre."""
    import uuid

    for _ in range(40):
        candidato = uuid.uuid4().hex[:12]
        r = cliente.post(
            f"/api/v1/participaciones/{participacion_id}/entregas",
            headers=auth(token),
            json={"repositorio": "https://github.com/demo/reto", "commit": candidato},
        )
        final = esperar(cliente, token, r.json()["evaluacion_id"])
        if final["dictamen"] == "APROBADO":
            return candidato
    raise AssertionError("no se encontro un commit aprobable")


def reto_fresco(cliente, titulo: str = "Reto de prueba") -> str:
    """Crea un reto publicado nuevo, para que cada prueba tenga su propia participacion."""
    from app.dominio.enums import CategoriaPrueba, EstadoReto
    from app.models import Prueba
    from app.models import Reto as RetoModelo
    from app.models._base import ahora

    with SessionLocal() as db:
        organizacion_id = db.scalar(select(RetoModelo.organizacion_id).limit(1))
        reto = RetoModelo(
            organizacion_id=organizacion_id,
            titulo=titulo,
            descripcion_publica="Caso sintetico.",
            criterios_aceptacion="Superar las obligatorias.",
            estado=EstadoReto.PUBLICADO,
            momento_publicacion=ahora(),
            repositorio_base="https://github.com/demo/reto",
            version_base="v1",
        )
        db.add(reto)
        db.flush()
        for i in range(4):
            db.add(
                Prueba(
                    reto_id=reto.id,
                    nombre=f"Prueba {i}",
                    categoria=CategoriaPrueba.FUNCIONAL,
                    obligatoria=i < 3,
                    condicion_aprobacion="Se cumple.",
                    referencia_ejecutable="t.py",
                )
            )
        db.commit()
        return str(reto.id)
