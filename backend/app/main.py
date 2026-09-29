import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import registrar_manejadores
from app.core.logging import configurar_logging, request_id

settings = get_settings()
configurar_logging(settings.LOG_LEVEL, settings.LOG_JSON)
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # El esquema lo aplica Alembic (`alembic upgrade head`), no el arranque de la aplicacion.
    # Las BackgroundTasks viven en memoria: si el proceso anterior murio con evaluaciones a medias,
    # nadie las va a terminar. Se cierran en ERROR_TECNICO para que el frontend deje de esperar.
    try:
        from app.servicios.evaluacion import cerrar_colgadas

        with SessionLocal() as db:
            cerradas = cerrar_colgadas(db, margen_s=0)
        if cerradas:
            log.warning("evaluaciones interrumpidas cerradas al arrancar", extra={"cantidad": cerradas})
    except Exception:  # noqa: BLE001 -- sin esquema todavia (primer arranque) no hay nada que cerrar
        log.exception("no se pudieron revisar evaluaciones interrumpidas")
    log.info(
        "servicio iniciado",
        extra={"entorno": settings.APP_ENV, "commit": settings.GIT_COMMIT, "evaluador": settings.EVALUADOR},
    )
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Lista blanca explicita: el frontend estatico vive en otro origen. Ver ADR-004.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,  # se usa Bearer, no cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

registrar_manejadores(app)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.middleware("http")
async def correlacionar(peticion: Request, siguiente):
    """Asigna un identificador a cada peticion y lo devuelve en la respuesta.

    Con `X-Request-ID` en la respuesta, un fallo reportado por el frontend se localiza en los
    logs sin adivinar."""
    rid = peticion.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    testigo = request_id.set(rid)
    inicio = time.perf_counter()
    try:
        respuesta = await siguiente(peticion)
    finally:
        request_id.reset(testigo)
    duracion = round((time.perf_counter() - inicio) * 1000, 1)
    respuesta.headers["X-Request-ID"] = rid
    log.info(
        "peticion atendida",
        extra={
            "metodo": peticion.method,
            "ruta": peticion.url.path,
            "estado": respuesta.status_code,
            "duracion_ms": duracion,
            "request_id": rid,
        },
    )
    return respuesta


@app.get("/health", tags=["sistema"])
def health():
    """Lo consulta el ping programado y lo abrira el jurado. Verifica la base de datos de verdad."""
    estado_bd = "ok"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        estado_bd = "error"
    return {
        "estado": "ok" if estado_bd == "ok" else "degradado",
        "base_datos": estado_bd,
        "version": settings.APP_VERSION,
        "commit": settings.GIT_COMMIT,
    }


@app.get(settings.API_V1_PREFIX + "/meta", tags=["sistema"])
def meta():
    """Declara con que motor se produce la telemetria. Transparencia deliberada, ver ADR-002."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "commit": settings.GIT_COMMIT,
        "entorno": settings.APP_ENV,
        "evaluador": settings.EVALUADOR,
        "preparador": settings.PREPARADOR,
        "llm_configurado": bool(settings.LLM_API_KEY),
        "llm_modelo": settings.LLM_MODEL if settings.LLM_API_KEY else None,
    }
