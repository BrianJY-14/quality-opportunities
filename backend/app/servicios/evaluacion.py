"""ServicioEvaluacion del UML.

Admite una entrega valida, solicita una evaluacion y la procesa con el evaluador. El actor de la
solicitud se valida antes del trabajo asincrono; el procesamiento posterior usa la identidad del
servicio y solicita certificacion al aprobar.
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturoVencido
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import ErrorDominio
from app.core.logging import evaluacion_id as ctx_evaluacion_id
from app.dominio.enums import (
    CondicionEjecucion,
    Dictamen,
    EstadoEvaluacion,
    OrigenEvento,
    ResultadoOperacion,
)
from app.models import Entrega, EspacioTrabajo, Evaluacion, Participacion, ResultadoPrueba, Usuario
from app.models._base import ahora
from app.servicios import auditoria, certificacion, juez_ia, seguridad
from app.servicios import workspace as servicio_workspace
from app.servicios.puertos import FalloEvaluador
from app.servicios.registro import obtener_evaluador

log = logging.getLogger("evaluacion")


def registrar_entrega(
    db: Session, participacion: Participacion, repositorio: str, commit: str, actor: Usuario
) -> Entrega:
    """RN-PART-03: exige reto habilitado y ausencia de credencial vigente en la participacion."""
    if not participacion.reto.admite_entregas():
        raise ErrorDominio(
            "RETO_NO_ADMITE_ENTREGAS",
            "El reto no admite nuevas entregas.",
            http=409,
            detalles={"estado": participacion.reto.estado},
        )

    if certificacion.credencial_vigente(db, participacion.id) is not None:
        raise ErrorDominio(
            "PARTICIPACION_YA_CERTIFICADA", "La participacion ya conserva una credencial vigente.", http=409
        )

    intentos = (
        db.scalar(select(func.count()).select_from(Entrega).where(Entrega.participacion_id == participacion.id)) or 0
    )

    # Regla 4: la entrega congela el proyecto del editor en el momento del envio. Seguir
    # editando el borrador despues no cambia lo que se evalua ni lo que revisa el juez.
    espacio = db.get(EspacioTrabajo, participacion.id)
    proyecto = espacio.archivos if espacio and servicio_workspace.leer_archivos(espacio.archivos) else None

    entrega = Entrega(
        participacion_id=participacion.id,
        numero_intento=intentos + 1,
        repositorio=repositorio,
        commit=commit,
        proyecto=proyecto,
        huella_proyecto=servicio_workspace.huella(proyecto) if proyecto else None,
    )
    db.add(entrega)
    db.flush()
    auditoria.registrar(db, "entrega.registrada", auditoria.referencia("entrega", entrega.id), actor=actor)
    return entrega


def solicitar(db: Session, entrega: Entrega, actor: Usuario) -> Evaluacion:
    """RN-EVAL-01: una entrega admite muchas evaluaciones. Reevaluar no exige entrega nueva.

    Devuelve la evaluacion en PENDIENTE; el procesamiento ocurre fuera del ciclo de peticion.
    """
    participacion = entrega.participacion
    if not participacion.reto.admite_entregas():
        raise ErrorDominio("RETO_NO_ADMITE_ENTREGAS", "El reto esta cerrado y no admite nuevos inicios.", http=409)
    if certificacion.credencial_vigente(db, participacion.id) is not None:
        raise ErrorDominio(
            "PARTICIPACION_YA_CERTIFICADA", "La participacion ya conserva una credencial vigente.", http=409
        )

    en_curso = db.scalar(
        select(Evaluacion).where(
            Evaluacion.entrega_id == entrega.id,
            Evaluacion.estado_procesamiento.in_((EstadoEvaluacion.PENDIENTE, EstadoEvaluacion.EN_EJECUCION)),
        )
    )
    if en_curso:
        raise ErrorDominio(
            "EVALUACION_EN_CURSO",
            "Ya hay una evaluacion en curso para esa entrega.",
            http=409,
            detalles={"evaluacion_id": str(en_curso.id)},
        )

    evaluacion = Evaluacion(
        entrega_id=entrega.id, version_evaluador="", estado_procesamiento=EstadoEvaluacion.PENDIENTE
    )
    db.add(evaluacion)
    db.flush()
    auditoria.registrar(db, "evaluacion.solicitada", auditoria.referencia("evaluacion", evaluacion.id), actor=actor)
    return evaluacion


def procesar(evaluacion_id: uuid.UUID) -> None:
    """Trabajo en segundo plano, con la identidad del servicio. Abre su propia sesion.

    Red de seguridad final: cualquier excepcion, tambien las que ocurran fuera del bloque que
    llama al evaluador (leer la entrega, persistir resultados, emitir), cierra la evaluacion en
    ERROR_TECNICO. Sin esto una fila podia quedar en EN_EJECUCION para siempre y el frontend
    consultando sin fin.
    """
    testigo = ctx_evaluacion_id.set(str(evaluacion_id))
    try:
        _procesar(evaluacion_id)
    except Exception as error:  # noqa: BLE001
        log.exception("fallo no controlado al procesar la evaluacion")
        with SessionLocal() as db:
            evaluacion = db.get(Evaluacion, evaluacion_id)
            if evaluacion is not None and evaluacion.estado_procesamiento in EN_CURSO:
                _cerrar_con_error_tecnico(db, evaluacion_id, f"Fallo interno al procesar: {type(error).__name__}")
    finally:
        ctx_evaluacion_id.reset(testigo)


EN_CURSO = (EstadoEvaluacion.PENDIENTE, EstadoEvaluacion.EN_EJECUCION)


def _ejecutar_con_limite(entrega, pruebas: list, archivos: list):
    """Llama al evaluador en un hilo aparte y espera como maximo LIMITE_EVALUACION_S.

    Un proveedor que no responde (el sandbox esperando su imagen, una conexion colgada) no puede
    retener la evaluacion: al vencer el plazo se levanta FalloEvaluador y la evaluacion cierra en
    ERROR_TECNICO. El hilo abandonado termina solo cuando el SDK corte; el sandbox tiene su propio
    tiempo de vida y se destruye al vencer.
    """
    limite = get_settings().LIMITE_EVALUACION_S
    ejecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="evaluador")
    futuro = ejecutor.submit(obtener_evaluador().ejecutar, entrega.repositorio, entrega.commit, pruebas, archivos)
    try:
        return futuro.result(timeout=limite)
    except FuturoVencido as error:
        raise FalloEvaluador(f"El entorno de ejecucion no respondio en {limite} s.") from error
    finally:
        ejecutor.shutdown(wait=False, cancel_futures=True)


def cerrar_colgadas(db: Session, margen_s: int | None = None) -> int:
    """Cierra en ERROR_TECNICO las evaluaciones que siguen en curso mas alla del limite.

    Cubre lo que ningun try/except puede cubrir: que el proceso muera a mitad del trabajo (Render
    reinicia o duerme el servicio del plan gratuito y las BackgroundTasks en memoria se pierden).
    Se llama al arrancar el servicio y al consultar una evaluacion.
    """
    limite = timedelta(seconds=(margen_s if margen_s is not None else get_settings().LIMITE_EVALUACION_S + 60))
    corte = ahora() - limite
    colgadas = db.scalars(
        select(Evaluacion).where(
            Evaluacion.estado_procesamiento.in_(EN_CURSO),
            func.coalesce(Evaluacion.momento_inicio, Evaluacion.momento_solicitud) < corte,
        )
    ).all()
    for evaluacion in colgadas:
        _cerrar_con_error_tecnico(
            db,
            evaluacion.id,
            "La evaluacion se interrumpio (reinicio del servicio o entorno sin respuesta). Se puede reevaluar.",
        )
    return len(colgadas)


def _procesar(evaluacion_id: uuid.UUID) -> None:
    with SessionLocal() as db:
        evaluacion = db.get(Evaluacion, evaluacion_id)
        if evaluacion is None or evaluacion.estado_procesamiento != EstadoEvaluacion.PENDIENTE:
            return  # ya fue tomada, o no existe

        # Una espera en cola no cuenta como inicio efectivo: el momento se fija aqui.
        evaluacion.estado_procesamiento = EstadoEvaluacion.EN_EJECUCION
        evaluacion.momento_inicio = ahora()
        db.commit()

        entrega = evaluacion.entrega
        pruebas = list(entrega.participacion.reto.pruebas)

        # El contenido que se ejecuta es la copia congelada de la entrega; si la entrega es
        # anterior a esa copia, el espacio de trabajo. El evaluador simulado lo ignora; el de
        # sandbox lo escribe y lo corre de verdad.
        if entrega.proyecto:
            archivos = servicio_workspace.leer_archivos(entrega.proyecto)
        else:
            espacio = db.get(EspacioTrabajo, entrega.participacion_id)
            archivos = servicio_workspace.leer_archivos(espacio.archivos) if espacio else []

        try:
            salida = _ejecutar_con_limite(entrega, pruebas, archivos)
        except FalloEvaluador as fallo:
            # RN-EVAL-03: el fallo del entorno se distingue de una solucion desaprobada.
            # Queda sin dictamen, y por tanto no puede sustentar una credencial.
            _cerrar_con_error_tecnico(db, evaluacion.id, str(fallo))
            return
        except Exception as error:  # noqa: BLE001 -- ninguna excepcion puede dejar la fila colgada
            # Sin esta rama, cualquier fallo no previsto (un tiempo de espera agotado contra el
            # proveedor de sandbox, una desconexion) deja la evaluacion en EN_EJECUCION para
            # siempre, y el frontend consultando su estado sin fin.
            log.exception("fallo inesperado del evaluador")
            _cerrar_con_error_tecnico(db, evaluacion.id, f"Fallo inesperado del evaluador: {type(error).__name__}")
            return

        evaluacion.version_evaluador = salida.version_evaluador
        for resultado in salida.resultados:
            db.add(
                ResultadoPrueba(
                    evaluacion_id=evaluacion.id,
                    prueba_id=resultado.prueba_id,
                    condicion_ejecucion=resultado.condicion_ejecucion,
                    aprobada=resultado.aprobada,
                    valor_observado=resultado.valor_observado,
                    unidad=resultado.unidad,
                    duracion_ms=resultado.duracion_ms,
                    detalle=resultado.detalle,
                )
            )
        db.flush()

        dictamen = _dictaminar(pruebas, salida.resultados)
        if dictamen is None:
            # Una comprobacion fallo por el entorno. Se conservan los resultados obtenidos y la
            # evaluacion cierra sin dictamen: RN-EVAL-03 prohibe cargarselo al estudiante.
            db.commit()
            _cerrar_con_error_tecnico(
                db, evaluacion.id, "Una comprobacion de la bateria no pudo ejecutarse por un fallo del entorno."
            )
            return

        evaluacion.dictamen = dictamen
        evaluacion.estado_procesamiento = EstadoEvaluacion.FINALIZADA
        evaluacion.momento_fin = ahora()
        auditoria.registrar(
            db,
            "evaluacion.finalizada",
            auditoria.referencia("evaluacion", evaluacion.id),
            origen=OrigenEvento.SISTEMA,
            detalle=f"dictamen={dictamen}",
        )
        db.flush()

        # Juez IA: revision de calidad del codigo. Informativa, no altera el dictamen, y un fallo
        # suyo no puede impedir ni la evaluacion ni la credencial.
        try:
            with db.begin_nested():
                juez_ia.revisar(db, evaluacion)
        except Exception:  # noqa: BLE001
            log.exception("el juez IA fallo; la evaluacion sigue su curso")

        if dictamen == Dictamen.APROBADO:
            try:
                certificacion.emitir(db, evaluacion)
            except ErrorDominio as error:
                # Que no se pueda emitir no invalida la evaluacion: queda aprobada y registrada.
                log.info("no se emitio credencial", extra={"codigo": error.codigo})

        db.commit()
        log.info(
            "evaluacion terminada",
            extra={
                "version_evaluador": salida.version_evaluador,
                "dictamen": dictamen,
                "pruebas": f"{sum(1 for r in salida.resultados if r.aprobada)}/{len(pruebas)}",
            },
        )


def _cerrar_con_error_tecnico(db: Session, evaluacion_id: uuid.UUID, motivo: str) -> None:
    """Cierra la evaluacion sin dictamen. Una evaluacion en ERROR_TECNICO no certifica.

    Se hace `rollback` primero porque la excepcion pudo dejar la sesion inutilizable, y en ese
    caso el propio registro del error no llegaria a escribirse.
    """
    db.rollback()
    evaluacion = db.get(Evaluacion, evaluacion_id)
    if evaluacion is None:
        return
    evaluacion.estado_procesamiento = EstadoEvaluacion.ERROR_TECNICO
    evaluacion.momento_fin = ahora()
    evaluacion.detalle_error = motivo
    auditoria.registrar(
        db,
        "evaluacion.error_tecnico",
        auditoria.referencia("evaluacion", evaluacion.id),
        ResultadoOperacion.ERROR,
        origen=OrigenEvento.SISTEMA,
        detalle=motivo,
    )
    db.commit()
    log.warning("evaluacion en error tecnico", extra={"motivo": motivo})


def _dictaminar(pruebas: list, resultados: list) -> str | None:
    """RN-EVAL-03: aprobar exige completar la bateria certificable y satisfacer todas las
    pruebas obligatorias.

    - `None`: alguna comprobacion fallo por el entorno. No es un veredicto sobre la solucion y
      quien llama lo traduce en ERROR_TECNICO.
    - NO_APROBADO: una prueba obligatoria SE EJECUTO y no se cumplio.
    - NO_EVALUABLE: ninguna obligatoria fallo, pero alguna no llego a ejecutarse (por ejemplo, el
      reto no define su codigo). "No ejecutada" no es "no cumplida": no aprueba ni certifica, pero
      tampoco se presenta al estudiante como desaprobacion.
    """
    por_prueba = {r.prueba_id: r for r in resultados}

    if any(r.condicion_ejecucion == CondicionEjecucion.ERROR_TECNICO for r in resultados):
        return None

    obligatorias = [p for p in pruebas if p.obligatoria]
    ejecutada = lambda p: p.id in por_prueba and por_prueba[p.id].condicion_ejecucion == CondicionEjecucion.EJECUTADA  # noqa: E731

    if any(ejecutada(p) and not por_prueba[p.id].aprobada for p in obligatorias):
        return Dictamen.NO_APROBADO
    if not all(ejecutada(p) for p in pruebas):
        return Dictamen.NO_EVALUABLE
    if any(not por_prueba[p.id].aprobada for p in obligatorias):
        return Dictamen.NO_APROBADO
    return Dictamen.APROBADO


def exigir_entrega_propia(db: Session, actor: Usuario, entrega_id: uuid.UUID) -> Entrega:
    """Error critico de la suite: nadie evalua la entrega de otra persona."""
    entrega = db.get(Entrega, entrega_id)
    if entrega is None:
        raise ErrorDominio("ENTREGA_NO_ENCONTRADA", "No existe esa entrega.", http=404)
    seguridad.participacion_propia(db, actor, entrega.participacion_id)
    return entrega
