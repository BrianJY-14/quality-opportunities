"""Datos de demostracion. Lo que se ve en el pitch sale de aqui.

Uso:  alembic upgrade head && python seed.py
Es idempotente: si ya hay retos, no vuelve a insertar.
"""

from sqlalchemy import inspect, select

from app.core.database import SessionLocal, engine
from app.core.security import hash_password
from app.dominio.enums import (
    CategoriaPrueba,
    EstadoPreparacion,
    EstadoReto,
    FuncionRepresentante,
    VisibilidadPerfil,
)
from app.models import (
    Organizacion,
    PerfilEstudiante,
    Prueba,
    Representacion,
    Reto,
    SolicitudReto,
    Usuario,
)
from app.models._base import ahora

CLAVE_DEMO = "demo12345"

PRUEBAS = [
    (
        "Contrato de la respuesta",
        CategoriaPrueba.FUNCIONAL,
        True,
        "La respuesta cumple el esquema acordado.",
        "tests/test_contrato.py",
        None,
    ),
    (
        "Entrada invalida",
        CategoriaPrueba.CASO_LIMITE,
        True,
        "La entrada invalida se rechaza sin efectos.",
        "tests/test_borde.py",
        None,
    ),
    (
        "Reintento duplicado",
        CategoriaPrueba.CASO_LIMITE,
        True,
        "Un reintento no duplica el efecto.",
        "tests/test_idempotencia.py",
        None,
    ),
    (
        "Concurrencia sostenida",
        CategoriaPrueba.FUNCIONAL,
        True,
        "No hay condiciones de carrera bajo carga.",
        "tests/test_concurrencia.py",
        None,
    ),
    (
        "Latencia bajo carga",
        CategoriaPrueba.RENDIMIENTO,
        False,
        "Percentil 95 por debajo de 50 ms.",
        "tests/test_carga.py",
        5000,
    ),
    (
        "Uso de memoria",
        CategoriaPrueba.RENDIMIENTO,
        False,
        "Sin crecimiento sostenido de memoria.",
        "tests/test_memoria.py",
        5000,
    ),
]

RETOS = [
    (
        "Idempotencia y concurrencia en una pasarela de pagos",
        "Durante campanas de alta demanda, reintentos de red desordenados provocan cobros duplicados.",
        "https://github.com/skill-hub/reto-idempotencia",
        "v1.0.0",
    ),
    (
        "Cache de lecturas para un catalogo de alta demanda",
        "El catalogo degrada su latencia cuando se multiplican las lecturas concurrentes.",
        "https://github.com/skill-hub/reto-cache",
        "v1.0.0",
    ),
    (
        "Pipeline ETL asincrono con validacion estricta",
        "La carga nocturna falla en silencio cuando el origen cambia de formato.",
        "https://github.com/skill-hub/reto-etl",
        "v1.0.0",
    ),
]


def main() -> None:
    if not inspect(engine).has_table("reto"):
        raise SystemExit("El esquema no existe. Ejecutar primero:  alembic upgrade head")

    with SessionLocal() as db:
        if db.scalar(select(Reto).limit(1)):
            print("Ya hay datos base sembrados; se omite la siembra base.")
        else:
            _sembrar_base(db)
        # Ampliacion para las funciones de IA: idempotente por titulo y por nombre publico, asi que
        # tambien se puede ejecutar sobre una base de produccion ya sembrada.
        import seed_ia

        seed_ia.ampliar(db)


def _sembrar_base(db) -> None:
    momento = ahora()

    organizacion = Organizacion(
        nombre="Banco Demo",
        descripcion="Organizacion de demostracion responsable de los retos publicados.",
        sitio_web="https://ejemplo.pe",
        logo="https://ejemplo.pe/logo.png",
    )
    db.add(organizacion)
    db.flush()

    # Representante: gestiona retos y puede revocar. No es un rol global.
    representante = Usuario(
        nombre="Ana Delgado", correo="representante@ejemplo.pe", hash_password=hash_password(CLAVE_DEMO)
    )
    db.add(representante)
    db.flush()
    db.add(
        Representacion(
            usuario_id=representante.id,
            organizacion_id=organizacion.id,
            funcion_autorizada=FuncionRepresentante.GESTOR_Y_REVOCADOR,
        )
    )

    # Estudiante de demostracion.
    estudiante = Usuario(nombre="Carlos Aranda", correo="carlos@uni.pe", hash_password=hash_password(CLAVE_DEMO))
    db.add(estudiante)
    db.flush()
    db.add(
        PerfilEstudiante(
            usuario_id=estudiante.id,
            nombre_publico="carlos-aranda",
            biografia="Backend, concurrencia y sistemas transaccionales.",
            visibilidad=VisibilidadPerfil.PUBLICO,
            universidad="UNI",
            carrera="Ingenieria de Sistemas",
            ciclo=7,
        )
    )

    # Una persona puede ser estudiante y representar a una organizacion a la vez (RN-ID-01).
    db.add(
        Representacion(
            usuario_id=estudiante.id,
            organizacion_id=organizacion.id,
            funcion_autorizada=FuncionRepresentante.GESTOR_RETOS,
            momento_inicio=momento,
        )
    )

    solicitud = SolicitudReto(
        representante_usuario_id=representante.id,
        organizacion_id=organizacion.id,
        titulo_original="Cobros duplicados en el endpoint de pagos",
        contenido_original_restringido="Caso sintetico de demostracion.",
        estado_preparacion=EstadoPreparacion.LISTA,
        modelo_ia="reglas:v1",
        version_instrucciones="2026.09.1",
        resumen_preparacion="Material saneado antes de proponer el borrador.",
    )
    db.add(solicitud)
    db.flush()

    for i, (titulo, contexto, repo, version) in enumerate(RETOS):
        reto = Reto(
            organizacion_id=organizacion.id,
            solicitud_id=solicitud.id if i == 0 else None,
            titulo=titulo,
            descripcion_publica=contexto,
            criterios_aceptacion=(
                "La solucion supera todas las pruebas obligatorias del reto y respeta las "
                "condiciones de rendimiento declaradas."
            ),
            estado=EstadoReto.PUBLICADO,
            momento_publicacion=momento,
            repositorio_base=repo,
            version_base=version,
        )
        db.add(reto)
        db.flush()
        for nombre, categoria, obligatoria, condicion, ref, limite in PRUEBAS:
            db.add(
                Prueba(
                    reto_id=reto.id,
                    nombre=nombre,
                    categoria=categoria,
                    obligatoria=obligatoria,
                    condicion_aprobacion=condicion,
                    referencia_ejecutable=ref,
                    limite_ejecucion_ms=limite,
                )
            )

    # Un reto en borrador, para demostrar la revision humana antes de publicar.
    borrador = Reto(
        organizacion_id=organizacion.id,
        titulo="Reintentos con backoff exponencial",
        descripcion_publica="Borrador propuesto por el preparador, pendiente de revision.",
        criterios_aceptacion="Pendiente de revision.",
        estado=EstadoReto.BORRADOR,
    )
    db.add(borrador)
    db.flush()
    db.add(
        Prueba(
            reto_id=borrador.id,
            nombre="Contrato de la respuesta",
            categoria=CategoriaPrueba.FUNCIONAL,
            obligatoria=True,
            condicion_aprobacion="La respuesta cumple el esquema acordado.",
            referencia_ejecutable="tests/test_contrato.py",
        )
    )

    db.commit()
    print(
        f"Sembrado: 1 organizacion, {len(RETOS)} retos publicados con {len(PRUEBAS)} pruebas "
        f"cada uno y 1 borrador.\n"
        f"  estudiante:     carlos@uni.pe / {CLAVE_DEMO}\n"
        f"  representante:  representante@ejemplo.pe / {CLAVE_DEMO}"
    )


if __name__ == "__main__":
    main()
