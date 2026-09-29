import { useEffect, useState } from 'react';

import { defensasDeEntrega, iniciarDefensa, responderDefensa } from '../service/api.js';
import { Aviso, Boton, Chip, Puntaje, Tarjeta, Titulo, colorPuntaje } from './ui.jsx';

const ENFOQUE = { DISENO: 'Diseño', CASO_LIMITE: 'Caso límite', ADAPTACION: 'Adaptación' };

/**
 * Defensa tecnica: el modelo pregunta por decisiones concretas del codigo entregado y califica
 * las respuestas. Demuestra comprension, no solo que las pruebas pasan.
 */
export default function DefensaPanel({ entregaId }) {
  const [defensa, setDefensa] = useState(null);
  const [historial, setHistorial] = useState([]);
  const [respuestas, setRespuestas] = useState({});
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!entregaId) return;
    defensasDeEntrega(entregaId)
      .then((lista) => {
        setHistorial(lista);
        const pendiente = lista.find((d) => d.estado === 'PENDIENTE');
        setDefensa(pendiente ?? lista[0] ?? null);
      })
      .catch(() => {});
  }, [entregaId]);

  const iniciar = async () => {
    setOcupado(true);
    setError(null);
    try {
      const d = await iniciarDefensa(entregaId);
      setDefensa(d);
      setRespuestas({});
    } catch (e) {
      setError(e.mensaje);
    } finally {
      setOcupado(false);
    }
  };

  const enviar = async () => {
    setOcupado(true);
    setError(null);
    try {
      const cuerpo = defensa.preguntas.map((p) => ({ pregunta_id: p.id, respuesta: (respuestas[p.id] ?? '').trim() }));
      const d = await responderDefensa(defensa.id, cuerpo);
      setDefensa(d);
      setHistorial((h) => [d, ...h.filter((x) => x.id !== d.id)]);
    } catch (e) {
      setError(e.codigo === 'VALIDACION' ? 'Cada respuesta necesita entre 20 y 1500 caracteres.' : e.mensaje);
    } finally {
      setOcupado(false);
    }
  };

  const pendiente = defensa?.estado === 'PENDIENTE';
  const completas = pendiente && defensa.preguntas.every((p) => (respuestas[p.id] ?? '').trim().length >= 20);
  const intentos = historial.length;

  return (
    <Tarjeta>
      <Titulo icono="record_voice_over" extra={defensa && <Chip title="Modelo que generó y calificó">{defensa.modelo}</Chip>}>
        Defensa técnica con IA
      </Titulo>

      {!defensa && (
        <>
          <p style={{ marginTop: 0 }}>
            El entrevistador IA lee el código entregado y hace tres preguntas sobre sus decisiones. Una defensa aprobada
            (60 o más) suma XP al ranking y queda como evidencia en el CV.
          </p>
          <Boton icono="play_arrow" onClick={iniciar} disabled={ocupado}>
            {ocupado ? 'Generando preguntas…' : 'Iniciar defensa'}
          </Boton>
        </>
      )}

      {pendiente && (
        <div className="qo-stack">
          {defensa.preguntas.map((p, i) => (
            <div key={p.id}>
              <div className="qo-tags" style={{ marginTop: 0, marginBottom: 8 }}>
                <span className="qo-tag cyan">
                  {i + 1} · {ENFOQUE[p.enfoque] ?? p.enfoque}
                </span>
                <span className="qo-tag">{p.archivo}</span>
              </div>
              <p style={{ color: 'var(--qo-text)', marginTop: 0 }}>{p.pregunta}</p>
              <textarea
                className="qo-textarea"
                rows={3}
                maxLength={1500}
                value={respuestas[p.id] ?? ''}
                onChange={(e) => setRespuestas((r) => ({ ...r, [p.id]: e.target.value }))}
                placeholder="Explicar con referencia a la implementación (mínimo 20 caracteres)."
              />
              <div className="qo-meta" style={{ textAlign: 'right' }}>{(respuestas[p.id] ?? '').length}/1500</div>
            </div>
          ))}
          <Boton icono="send" onClick={enviar} disabled={!completas || ocupado}>
            {ocupado ? 'Calificando…' : 'Enviar respuestas'}
          </Boton>
        </div>
      )}

      {defensa && !pendiente && (
        <div className="qo-stack">
          <div className="qo-actions" style={{ gap: 20 }}>
            <Puntaje valor={defensa.puntaje} tamaño={42} etiqueta="Defensa" />
            <div>
              <h3 style={{ margin: 0 }}>
                {defensa.estado === 'SIN_CALIFICAR'
                  ? 'Respuestas guardadas sin calificar'
                  : defensa.aprobada
                    ? 'Defensa aprobada'
                    : 'Defensa no aprobada'}
              </h3>
              <span className="qo-meta">
                Umbral {defensa.umbral_aprobacion} · intento {intentos} de 3
              </span>
            </div>
          </div>
          {defensa.retroalimentacion && <Aviso>{defensa.retroalimentacion}</Aviso>}
          <div className="qo-list">
            {defensa.preguntas.map((p, i) => {
              const c = defensa.calificaciones?.[p.id];
              return (
                <div key={p.id} className="qo-row">
                  <div style={{ flex: 1 }}>
                    <h3>
                      {i + 1}. {p.pregunta}
                    </h3>
                    <p style={{ fontStyle: 'italic' }}>“{defensa.respuestas?.[p.id]}”</p>
                    {c?.comentario && <p style={{ color: 'var(--qo-mint)', fontSize: 13, marginTop: 6 }}>{c.comentario}</p>}
                  </div>
                  {c && <strong style={{ fontSize: 22, color: colorPuntaje(c.puntaje) }}>{c.puntaje}</strong>}
                </div>
              );
            })}
          </div>
          {!defensa.aprobada && intentos < 3 && (
            <Boton variante="secundario" icono="replay" onClick={iniciar} disabled={ocupado}>
              Nueva defensa con otras preguntas
            </Boton>
          )}
        </div>
      )}

      {error && <p style={{ color: '#ffb4ab', fontSize: 14 }}>{error}</p>}
    </Tarjeta>
  );
}
