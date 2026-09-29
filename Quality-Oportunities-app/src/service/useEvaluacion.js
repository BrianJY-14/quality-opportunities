import { useState } from 'react';

import { enviarEntrega, esperarEvaluacion, reevaluar } from './api.js';

/**
 * Envio de una solucion y seguimiento de su evaluacion.
 *
 * `estado` refleja lo que informa el backend, no una animacion: PENDIENTE significa que el trabajo
 * existe y EN_EJECUCION que ya empezo. `progreso` trae pruebas ejecutadas sobre totales, contadas
 * de filas realmente escritas.
 */
export function useEvaluacion() {
  const [situacion, setSituacion] = useState('idle'); // idle | enviando | corriendo | listo | error
  const [evaluacion, setEvaluacion] = useState(null);
  const [error, setError] = useState(null);

  const enviar = async (participacionId, { repositorio, commit }) => {
    setSituacion('enviando');
    setError(null);
    setEvaluacion(null);
    try {
      const aceptada = await enviarEntrega(participacionId, { repositorio, commit });
      setSituacion('corriendo');
      const final = await esperarEvaluacion(aceptada.evaluacion_id, setEvaluacion);
      setEvaluacion(final);
      setSituacion('listo');
      return final;
    } catch (e) {
      setError(e);
      setSituacion('error');
      return null;
    }
  };

  const volverAEvaluar = async (entregaId) => {
    setSituacion('corriendo');
    setError(null);
    try {
      const aceptada = await reevaluar(entregaId);
      const final = await esperarEvaluacion(aceptada.evaluacion_id, setEvaluacion);
      setEvaluacion(final);
      setSituacion('listo');
      return final;
    } catch (e) {
      setError(e);
      setSituacion('error');
      return null;
    }
  };

  // Tres finales distintos, y cada uno pide una pantalla distinta. Un fallo del entorno no es una
  // desaprobacion del estudiante y no debe presentarse como tal.
  const aprobada = evaluacion?.dictamen === 'APROBADO';
  const desaprobada = evaluacion?.dictamen === 'NO_APROBADO';
  const errorTecnico = evaluacion?.estado_procesamiento === 'ERROR_TECNICO';
  const noEvaluable = evaluacion?.dictamen === 'NO_EVALUABLE';

  return {
    enviar,
    volverAEvaluar,
    situacion,
    evaluacion,
    error,
    aprobada,
    desaprobada,
    errorTecnico,
    noEvaluable,
    progreso: evaluacion?.progreso ?? null,
    resultados: evaluacion?.resultados ?? [],
    credencial: evaluacion?.credencial ?? null,
  };
}
