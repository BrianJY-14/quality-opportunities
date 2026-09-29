import { useEffect, useState } from 'react';

import { Aviso, Cargando, Chip, Encabezado, Icono, Pagina, colorPuntaje } from '../../components/ui.jsx';
import { ranking } from '../../service/api.js';

export const COLOR_RANGO = {
  CACHIMBO: '#22c55e',
  JUNIOR_BUILDER: '#3b82f6',
  MID_ARCHITECT: '#a855f7',
  SENIOR_SINNER: '#ef4444',
  ORACULO_TECH: '#eab308',
};

export function InsigniaRango({ rango }) {
  return (
    <span className="qo-rango" style={{ color: COLOR_RANGO[rango.codigo] ?? COLOR_RANGO.CACHIMBO }}>
      <Icono nombre="military_tech" />
      {rango.nombre}
    </span>
  );
}

/** Leaderboard de solucionadores: XP ponderada por dificultad, Juez IA y defensa. */
export default function RankingPage({ onVerPerfil }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    ranking(100).then(setDatos).catch(setError);
  }, []);

  return (
    <Pagina>
      <Encabezado
        eyebrow="LEADERBOARD // CACHIMBO → ORÁCULO"
        titulo="Solucionadores con evidencia."
        descripcion="La posición no premia volumen: cada credencial vigente suma XP según la dificultad del reto, la calidad medida por el Juez IA y la defensa técnica aprobada."
      />

      {datos && (
        <div className="qo-grid cinco" style={{ marginBottom: 26 }}>
          {datos.rangos.map((r) => (
            <div key={r.codigo} className="qo-kpi" style={{ borderTop: `2px solid ${COLOR_RANGO[r.codigo]}` }}>
              <small style={{ color: COLOR_RANGO[r.codigo] }}>{r.nombre}</small>
              <strong style={{ fontSize: 18 }}>{r.umbral_xp} XP</strong>
              <span className="qo-meta">{r.beneficio}</span>
            </div>
          ))}
        </div>
      )}

      {error && <Aviso tipo="error">{error.mensaje}</Aviso>}
      {!datos && !error && <Cargando texto="Calculando posiciones…" />}
      {datos && !datos.filas.length && <Aviso>Todavía no hay perfiles públicos con credenciales vigentes.</Aviso>}

      {datos && datos.filas.length > 0 && (
        <div className="qo-board">
          <div className="qo-board-row head">
            <span>#</span>
            <span>Solucionador</span>
            <span className="ocultar-movil">Rango</span>
            <span className="ocultar-movil" style={{ textAlign: 'right' }}>
              XP
            </span>
            <span className="ocultar-movil" style={{ textAlign: 'right' }}>
              Juez IA
            </span>
            <span className="ocultar-movil">Aptitudes</span>
          </div>
          {datos.filas.map((f) => (
            <button key={f.nombre_publico} type="button" className="qo-board-row" onClick={() => onVerPerfil?.(f.nombre_publico)}>
              <span className="qo-board-pos" style={{ color: f.posicion === 1 ? '#eab308' : f.posicion <= 3 ? 'var(--qo-cyan)' : undefined }}>
                {f.posicion}
              </span>
              <span style={{ minWidth: 0 }}>
                <strong style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.nombre_publico}</strong>
                <span className="qo-meta">
                  {[f.universidad, f.carrera].filter(Boolean).join(' · ')} · {f.credenciales} credencial{f.credenciales === 1 ? '' : 'es'}
                </span>
              </span>
              <span className="ocultar-movil">
                <InsigniaRango rango={f.rango} />
              </span>
              <strong className="ocultar-movil" style={{ textAlign: 'right', color: 'var(--qo-yellow)' }}>
                {f.xp}
              </strong>
              <strong className="ocultar-movil" style={{ textAlign: 'right', color: colorPuntaje(f.promedio_juez_ia) }}>
                {f.promedio_juez_ia ?? '—'}
              </strong>
              <span className="ocultar-movil qo-tags" style={{ marginTop: 0 }}>
                {f.aptitudes_top.map((a) => (
                  <Chip key={a} tono="primario">
                    {a}
                  </Chip>
                ))}
              </span>
              <strong className="solo-movil" style={{ color: 'var(--qo-yellow)' }}>
                {f.xp} XP
              </strong>
            </button>
          ))}
        </div>
      )}
      <p className="qo-meta" style={{ marginTop: 16 }}>
        Solo aparecen perfiles públicos. Los terminados en “-demo” son datos de demostración sembrados para la presentación.
      </p>
    </Pagina>
  );
}
