import json

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.core.database import get_db
from app.models import Credencial, Usuario
from app.schemas.credencial import CredencialSalida, RevocacionEntrada, RevocacionSalida
from app.servicios import certificacion, seguridad

router = APIRouter()


def a_salida(credencial: Credencial) -> CredencialSalida:
    """El contenido emitido conserva su presentacion historica (RN-CRED-02): la respuesta se
    arma desde `contenido_emitido`, no desde el estado actual del perfil o del reto."""
    contenido = json.loads(credencial.contenido_emitido)
    reto = credencial.participacion.reto
    # Credenciales corregidas a mano en la base durante el hackaton guardaron los criterios como
    # lista y algunas omiten claves. La respuesta se arma con lo que haya, sin 500.
    criterios = contenido.get("criterios_aceptacion", reto.criterios_aceptacion)
    if isinstance(criterios, list):
        criterios = "\n".join(str(c) for c in criterios)
    return CredencialSalida(
        identificador_publico=credencial.identificador_publico,
        vigente=credencial.esta_vigente(),
        momento_emision=credencial.momento_emision,
        emisor=contenido.get("emisor", reto.organizacion.nombre),
        emisor_logo=reto.organizacion.logo,
        estudiante=contenido.get("estudiante", credencial.participacion.perfil.nombre_publico),
        reto=contenido.get("reto", reto.titulo),
        criterios_aceptacion=str(criterios),
        commit=contenido.get("commit", ""),
        repositorio=contenido.get("repositorio", ""),
        version_evaluador=contenido.get("version_evaluador", "desconocida"),
        huella_contenido=credencial.huella_contenido,
        revocacion=RevocacionSalida(
            momento_revocacion=credencial.revocacion.momento_revocacion,
            motivo=credencial.revocacion.motivo,
        )
        if credencial.revocacion
        else None,
    )


@router.get("/credenciales/{identificador_publico}", response_model=CredencialSalida)
def consultar(identificador_publico: str, db: Session = Depends(get_db)):
    """Consulta publica: el reclutador verifica sin cuenta.

    Informa por separado sobre el contenido emitido y sobre la vigencia."""
    return a_salida(certificacion.consultar(db, identificador_publico))


@router.post(
    "/credenciales/{identificador_publico}/revocacion",
    response_model=CredencialSalida,
    status_code=status.HTTP_201_CREATED,
)
def revocar(
    identificador_publico: str,
    datos: RevocacionEntrada,
    db: Session = Depends(get_db),
    actor: Usuario = Depends(usuario_actual),
):
    """Operacion del portal autorizado. Ser dueno del perfil no concede este permiso."""
    credencial = certificacion.consultar(db, identificador_publico)
    seguridad.exigir_revocacion(
        db,
        actor,
        credencial.participacion.reto.organizacion_id,
        "credencial.revocada",
        f"credencial:{identificador_publico}",
    )

    certificacion.revocar(db, credencial, datos.motivo, actor)
    db.commit()
    db.refresh(credencial)
    return a_salida(credencial)
