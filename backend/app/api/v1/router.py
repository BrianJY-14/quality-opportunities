from fastapi import APIRouter

from app.api.v1 import (
    auth,
    credenciales,
    entregas,
    ia,
    participaciones,
    perfiles,
    retos,
    solicitudes,
    workspace,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(retos.router, tags=["retos"])
api_router.include_router(solicitudes.router, tags=["solicitudes"])
api_router.include_router(participaciones.router, tags=["participaciones"])
api_router.include_router(workspace.router, tags=["espacio de trabajo"])
api_router.include_router(entregas.router, tags=["entregas y evaluaciones"])
api_router.include_router(credenciales.router, tags=["credenciales"])
api_router.include_router(perfiles.router, tags=["perfiles"])
api_router.include_router(ia.router)
