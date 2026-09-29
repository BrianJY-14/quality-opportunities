import { useEffect, useState } from 'react';

import DefensaPanel from '../../components/DefensaPanel.jsx';
import JuezIAPanel from '../../components/JuezIAPanel.jsx';
import { Aviso, Boton, Cargando, Chip, Encabezado, Icono, Pagina, Tarjeta, Titulo } from '../../components/ui.jsx';
import { reevaluar, reintentarRevisionIA, verEvaluacion } from '../../service/api.js';

const EN_CURSO = ['PENDIENTE', 'EN_EJECUCION'];

/**
 * Resultado real de una evaluacion.
 *
 * Recibe `evaluacionId` de la pagina anterior y consulta el estado hasta que termina. Los tres
 * finales posibles se muestran distinto, y el fallo de entorno NO se presenta como una
 * desaprobacion del estudiante.
 */
export default function ResultadoPage({ evaluacionId, tituloReto, onVolver, onVerCV }) {
  const [idActual, setIdActual] = useState(evaluacionId);
  const [evaluacion, setEvaluacion] = useState(null);
  const [error, setError] = useState(null);
  const [agotado, setAgotado] = useState(false);

  useEffect(() => setIdActual(evaluacionId), [evaluacionId]);

  useEffect(() => {
    if (!idActual) return undefined;
    let vigente = true;
    const inicio = Date.now();
    setAgotado(false);

    // Consulta con espera creciente y un techo: aunque el backend ya cierra las evaluaciones
    // colgadas, la pantalla no vuelve a quedarse consultando para siempre.
    const consultar = async (espera) => {
      try {
        const estado = await verEvaluacion(idActual);
        if (!vigente) return;
        setEvaluacion(estado);
        if (!EN_CURSO.includes(estado.estado_procesamiento)) return;
        if (Date.now() - inicio > 6 * 60 * 1000) {
          setAgotado(true);
          return;
        }
        setTimeout(() => consultar(Math.min(espera * 1.3, 5000)), espera);
      } catch (e) {
        if (vigente) setError(e);
      }
    };
    consultar(800);

    return () => {
      vigente = false;
    };
  }, [idActual]);

  const reintentar = async () => {
    try {
      const nueva = await reevaluar(evaluacion.entrega_id);
      setEvaluacion(null);
      setIdActual(nueva.evaluacion_id);
    } catch (e) {
      setError(e);
    }
  };

  const enCurso = evaluacion && EN_CURSO.includes(evaluacion.estado_procesamiento);
  const aprobado = evaluacion?.dictamen === 'APROBADO';
  const errorTecnico = evaluacion?.estado_procesamiento === 'ERROR_TECNICO';
  // Ninguna prueba obligatoria llego a ejecutarse: no es una desaprobacion.
  const noEvaluable = evaluacion?.dictamen === 'NO_EVALUABLE';
  const progreso = evaluacion?.progreso;
  const porcentaje = progreso?.pruebas_totales
    ? Math.round((progreso.pruebas_ejecutadas / progreso.pruebas_totales) * 100)
    : 0;

  const CATEGORIA = { FUNCIONAL: 'Funcional', CASO_LIMITE: 'Caso límite', RENDIMIENTO: 'Rendimiento' };
  const clase = errorTecnico || noEvaluable ? 'tec' : aprobado ? 'ok' : 'no';
  const duracion =
    evaluacion?.momento_inicio && evaluacion?.momento_fin
      ? Math.round((new Date(evaluacion.momento_fin) - new Date(evaluacion.momento_inicio)) / 10) / 100
      : null;

  return (
    <Pagina>
      <Boton variante="fantasma" icono="arrow_back" onClick={onVolver}>
        Volver al catálogo
      </Boton>
      <Encabezado eyebrow="EVALUACIÓN // PRUEBAS OFICIALES + JUEZ IA" titulo="Resultado de la evaluación" descripcion={tituloReto} />

      <div className="qo-stack">
        {error && <Aviso tipo="error">{error.mensaje}</Aviso>}
        {!evaluacion && !error && <Cargando texto="Cargando la evaluación…" />}

        {enCurso && (
          <Tarjeta>
            <div className="qo-actions" style={{ justifyContent: 'space-between' }}>
              <span className="qo-actions">
                <span className="qo-pulse" />
                <strong>{evaluacion.estado_procesamiento === 'PENDIENTE' ? 'En cola' : 'En ejecución'}</strong>
              </span>
              {progreso && (
                <span className="qo-meta">
                  {progreso.pruebas_ejecutadas} / {progreso.pruebas_totales} pruebas ({porcentaje}%)
                </span>
              )}
            </div>
            <div className="qo-progress">
              <span style={{ width: `${porcentaje}%` }} />
            </div>
            <p className="qo-meta" style={{ marginBottom: 0 }}>
              Al terminar las pruebas, el Juez IA revisa el código: puede sumar unos segundos.
            </p>
          </Tarjeta>
        )}

        {agotado && (
          <Aviso tipo="aviso">
            La evaluación sigue en curso después de 6 minutos. Se dejó de consultar para no bloquear la pantalla; el
            servidor la cerrará como error técnico si el entorno no responde.
          </Aviso>
        )}

        {evaluacion && !enCurso && (
          <>
            <div className={`qo-veredicto ${clase}`}>
              <Icono
                nombre={errorTecnico ? 'build' : noEvaluable ? 'help' : aprobado ? 'verified' : 'cancel'}
                style={{
                  color: errorTecnico || noEvaluable ? 'var(--qo-yellow)' : aprobado ? 'var(--qo-mint)' : '#ffb4ab',
                }}
              />
              <div style={{ flex: 1 }}>
                <h2 style={{ margin: 0 }}>
                  {errorTecnico
                    ? 'No se pudo completar la evaluación'
                    : noEvaluable
                      ? 'No evaluable'
                      : aprobado
                        ? 'Aprobado'
                        : 'No aprobado'}
                </h2>
                <p style={{ margin: '4px 0 0' }}>
                  {errorTecnico
                    ? evaluacion.detalle_error ?? 'Fallo del entorno de ejecución. No cuenta como desaprobación.'
                    : noEvaluable
                      ? 'Alguna prueba del reto no llegó a ejecutarse (el reto no define su código). No cuenta como desaprobación ni emite credencial.'
                      : aprobado
                        ? 'La solución superó todas las pruebas obligatorias del reto.'
                        : 'Una prueba obligatoria se ejecutó y no se cumplió.'}
                </p>
              </div>
              {errorTecnico && (
                <Boton variante="secundario" icono="replay" onClick={reintentar}>
                  Reevaluar
                </Boton>
              )}
            </div>

            {evaluacion.credencial && (
              <Tarjeta className="certificate">
                <div className="qo-certificate-art" style={{ margin: 0, minHeight: 120, '--accent': 'var(--qo-mint)' }}>
                  <Icono nombre="workspace_premium" />
                  <small>CREDENCIAL {evaluacion.credencial.identificador_publico}</small>
                </div>
                <div className="qo-cert-meta">
                  <span>{evaluacion.credencial.vigente ? 'Vigente' : 'Revocada'} · verificable de forma pública</span>
                  {onVerCV && (
                    <button className="qo-btn ghost small" onClick={onVerCV}>
                      <Icono nombre="hub" /> Ver el CV actualizado
                    </button>
                  )}
                </div>
              </Tarjeta>
            )}
            {aprobado && !evaluacion.credencial && <Aviso>Evaluación aprobada; emisión de la credencial pendiente.</Aviso>}

            {evaluacion.resultados?.length > 0 && (
              <Tarjeta>
                <Titulo icono="checklist">Pruebas ejecutadas</Titulo>
                <div className="qo-list">
                  {evaluacion.resultados.map((r) => {
                    const ejecutada = r.condicion_ejecucion === 'EJECUTADA';
                    return (
                      <div key={r.prueba_id} className="qo-row" style={{ justifyContent: 'flex-start' }}>
                        <Icono
                          nombre={!ejecutada ? 'remove' : r.aprobada ? 'check_circle' : 'cancel'}
                          style={{ color: !ejecutada ? '#7f8f94' : r.aprobada ? 'var(--qo-mint)' : '#ffb4ab' }}
                        />
                        <div style={{ flex: 1 }}>
                          <h3>{r.prueba}</h3>
                          <div className="qo-tags" style={{ marginTop: 6 }}>
                            <span className="qo-tag">{CATEGORIA[r.categoria] ?? r.categoria}</span>
                            {r.obligatoria && <span className="qo-tag cyan">obligatoria</span>}
                            {r.duracion_ms != null && <span className="qo-tag">{r.duracion_ms} ms</span>}
                            {r.valor_observado != null && (
                              <span className="qo-tag">
                                {r.valor_observado} {r.unidad}
                              </span>
                            )}
                            {!ejecutada && <span className="qo-tag gold">{r.condicion_ejecucion}</span>}
                          </div>
                          {r.detalle && <p className="qo-meta" style={{ marginTop: 8 }}>{r.detalle}</p>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Tarjeta>
            )}

            <JuezIAPanel
              revision={evaluacion.revision_ia}
              onReintentar={async () => {
                const revision = await reintentarRevisionIA(evaluacion.id ?? idActual);
                setEvaluacion((e) => ({ ...e, revision_ia: revision }));
              }}
            />
            {evaluacion.revision_ia && evaluacion.revision_ia.estado !== 'SIN_CODIGO' && (
              <DefensaPanel entregaId={evaluacion.entrega_id} />
            )}

            {/* El motor que produjo el resultado viaja siempre: nada afirma una ejecucion que no ocurrio. */}
            <div className="qo-tags" style={{ marginTop: 0 }}>
              <Chip>Motor: {evaluacion.version_evaluador || '—'}</Chip>
              {duracion != null && <Chip>Duración: {duracion} s</Chip>}
            </div>
          </>
        )}
      </div>
    </Pagina>
  );
}
