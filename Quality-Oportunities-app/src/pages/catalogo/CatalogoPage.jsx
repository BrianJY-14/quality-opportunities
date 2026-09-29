import { useMemo, useState } from 'react';

import { Aviso, Boton, Cargando, Chip, Encabezado, Filtros, Icono, Pagina } from '../../components/ui.jsx';
import { useRetos } from '../../service/useRetos.js';

const ACENTO = { BASICO: '#4edea3', INTERMEDIO: '#4cd7f6', AVANZADO: '#eec200' };
const ICONO = { BASICO: 'school', INTERMEDIO: 'deployed_code', AVANZADO: 'bolt' };

/** Catalogo de retos publicados, con las tarjetas de proyecto de la maqueta. */
export default function CatalogoPage({ onSelectReto }) {
  const { retos, cargando, error } = useRetos();
  const [filtro, setFiltro] = useState('todos');
  const [busqueda, setBusqueda] = useState('');

  const visibles = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    return retos.filter(
      (r) =>
        (filtro === 'todos' || r.dificultad === filtro) &&
        (!q || [r.titulo, r.org, ...(r.aptitudes ?? [])].some((t) => t.toLowerCase().includes(q))),
    );
  }, [retos, filtro, busqueda]);

  const cuenta = (d) => retos.filter((r) => r.dificultad === d).length;

  return (
    <Pagina>
      <Encabezado
        eyebrow="RETOS // CATÁLOGO PUBLICADO"
        titulo="Retos de ingeniería con evidencia verificable."
        descripcion="Problemas de organizaciones convertidos en retos por el AI Scoper, evaluados con pruebas automáticas, revisados por el Juez IA y defendidos ante el entrevistador IA."
        acciones={
          <div className="qo-grid" style={{ gridTemplateColumns: 'repeat(3, minmax(96px, 1fr))', gap: 10 }}>
            {[
              ['Publicados', retos.length, 'var(--qo-cyan)'],
              ['Organizaciones', new Set(retos.map((r) => r.org)).size, 'var(--qo-yellow)'],
              ['Avanzados', cuenta('AVANZADO'), 'var(--qo-mint)'],
            ].map(([t, v, c]) => (
              <div className="qo-kpi" key={t}>
                <small>{t}</small>
                <strong style={{ color: c }}>{v}</strong>
              </div>
            ))}
          </div>
        }
      />

      <div className="qo-toolbar">
        <Filtros
          valor={filtro}
          onCambio={setFiltro}
          opciones={[
            ['todos', `Todos · ${retos.length}`],
            ['BASICO', `Básico · ${cuenta('BASICO')}`],
            ['INTERMEDIO', `Intermedio · ${cuenta('INTERMEDIO')}`],
            ['AVANZADO', `Avanzado · ${cuenta('AVANZADO')}`],
          ]}
        />
        <input
          className="qo-search"
          type="search"
          placeholder="Buscar reto, aptitud u organización…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
      </div>

      {error && <Aviso tipo="error">{error.mensaje}</Aviso>}
      {cargando && <Cargando texto="Cargando el catálogo (el servidor gratuito puede tardar en despertar)…" />}

      <div className="qo-grid">
        {visibles.map((r) => (
          <article key={r.id} className="qo-card project" style={{ '--accent': ACENTO[r.dificultad] ?? 'var(--qo-cyan)' }}>
            <div className="qo-card-top">
              <span className="qo-project-icon">
                <Icono nombre={ICONO[r.dificultad] ?? 'code'} />
              </span>
              <Chip tono={r.estado === 'abierto' ? 'exito' : 'neutro'}>{r.estado === 'abierto' ? 'Abierto' : 'Cerrado'}</Chip>
            </div>
            <div className="qo-meta">
              {r.org.toUpperCase()} // {r.dificultad} · {r.puntos} XP BASE
            </div>
            <h3>{r.titulo}</h3>
            <p style={{ margin: 0, fontSize: 14 }}>
              {r.pruebasObligatorias} de {r.pruebasTotales} pruebas obligatorias.
            </p>
            <div className="qo-tags">
              {(r.aptitudes?.length ? r.aptitudes : r.stack).slice(0, 4).map((a) => (
                <span key={a} className="qo-tag">
                  {a}
                </span>
              ))}
            </div>
            <div className="qo-actions">
              <Boton variante="secundario" icono="arrow_forward" onClick={() => onSelectReto?.(r)}>
                Ver reto
              </Boton>
            </div>
          </article>
        ))}
        {!cargando && !visibles.length && <div className="qo-empty">Ningún reto coincide con la búsqueda.</div>}
      </div>
    </Pagina>
  );
}
