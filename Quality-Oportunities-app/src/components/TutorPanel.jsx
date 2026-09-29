import { useState } from 'react';

import { consultarTutor } from '../service/api.js';
import { Boton, Chip, Icono, Tarjeta, Titulo } from './ui.jsx';

const COLOR = { ERROR: '#ffb4ab', ADVERTENCIA: 'var(--qo-yellow)', INFO: 'var(--qo-cyan)' };
const ICONO = { ERROR: 'error', ADVERTENCIA: 'warning', INFO: 'lightbulb' };

/**
 * Tutor IA dentro del editor. Antes de consultar se guarda, porque el backend analiza la
 * revision GUARDADA: asi la respuesta siempre corresponde a un codigo identificable.
 */
export default function TutorPanel({ participacionId, guardarAntes, sucio, onIrALinea }) {
  const [pregunta, setPregunta] = useState('');
  const [respuesta, setRespuesta] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  const consultar = async () => {
    if (!participacionId || ocupado) return;
    setOcupado(true);
    setError(null);
    try {
      if (sucio) await guardarAntes();
      setRespuesta(await consultarTutor(participacionId, pregunta.trim()));
    } catch (e) {
      setError(e.mensaje ?? 'El tutor no respondió.');
    } finally {
      setOcupado(false);
    }
  };

  return (
    <Tarjeta>
      <Titulo
        icono="psychology"
        extra={
          respuesta && (
            <Chip tono={respuesta.modo === 'IA' ? 'exito' : 'neutro'} title={respuesta.modelo}>
              {respuesta.modo === 'IA' ? 'modelo' : 'reglas'} · rev {respuesta.revision}
            </Chip>
          )
        }
      >
        Tutor IA
      </Titulo>

      <textarea
        className="qo-textarea"
        value={pregunta}
        onChange={(e) => setPregunta(e.target.value)}
        maxLength={600}
        rows={2}
        placeholder="Pregunta sobre el código (opcional). El tutor da pistas, no soluciones."
      />
      <Boton icono={ocupado ? 'hourglass_top' : 'tips_and_updates'} onClick={consultar} disabled={ocupado || !participacionId} className="w-full" variante="secundario">
        {ocupado ? 'Analizando…' : 'Pedir pista'}
      </Boton>

      {error && <p style={{ color: '#ffb4ab', fontSize: 14 }}>{error}</p>}

      {respuesta && (
        <div className="qo-list" style={{ marginTop: 14, maxHeight: 440, overflowY: 'auto' }}>
          {respuesta.respuesta && <div className="qo-note">{respuesta.respuesta}</div>}
          {respuesta.diagnosticos.map((d, i) => (
            <button key={i} type="button" className="qo-row" style={{ justifyContent: 'flex-start' }} onClick={() => onIrALinea?.(d.archivo, d.linea)}>
              <Icono nombre={ICONO[d.severidad] ?? 'info'} style={{ color: COLOR[d.severidad] ?? 'var(--qo-cyan)', fontSize: 20 }} />
              <span>
                <span className="qo-meta">
                  {d.archivo}
                  {d.linea ? `:${d.linea}` : ''} · {d.origen}
                </span>
                <p style={{ color: 'var(--qo-text)' }}>{d.mensaje}</p>
                {d.pista && <p style={{ fontSize: 13 }}>Pista: {d.pista}</p>}
              </span>
            </button>
          ))}
          {respuesta.siguiente_paso && (
            <p style={{ fontSize: 14, color: 'var(--qo-mint)', margin: 0 }}>
              <strong>Siguiente paso:</strong> {respuesta.siguiente_paso}
            </p>
          )}
          {respuesta.conceptos?.length > 0 && (
            <div className="qo-tags" style={{ marginTop: 0 }}>
              {respuesta.conceptos.map((c) => (
                <Chip key={c} tono="primario">
                  {c}
                </Chip>
              ))}
            </div>
          )}
          <span className="qo-meta">{respuesta.aviso}</span>
        </div>
      )}
    </Tarjeta>
  );
}
