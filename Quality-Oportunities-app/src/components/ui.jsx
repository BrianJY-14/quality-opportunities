/**
 * Piezas visuales compartidas, sobre el sistema qo-* (estilos/qo.css) de la maqueta "Demo local".
 * Todas las pantallas se construyen con estas piezas para que el lenguaje visual sea uno solo.
 */

export function Icono({ nombre, className = '', style }) {
  return (
    <span className={`material-symbols-outlined ${className}`} style={style} aria-hidden="true">
      {nombre}
    </span>
  );
}

export function Pagina({ children }) {
  return <main className="qo-main">{children}</main>;
}

export function Encabezado({ eyebrow, titulo, descripcion, acciones }) {
  return (
    <div className="qo-page-head">
      <div>
        {eyebrow && <div className="qo-eyebrow">{eyebrow}</div>}
        <h1>{titulo}</h1>
        {descripcion && <p>{descripcion}</p>}
      </div>
      {acciones && <div className="qo-actions">{acciones}</div>}
    </div>
  );
}

export function Tarjeta({ children, className = '', style }) {
  return (
    <section className={`qo-card ${className}`} style={style}>
      {children}
    </section>
  );
}

export function Titulo({ icono, children, extra }) {
  return (
    <div className="qo-card-top" style={{ marginBottom: 18 }}>
      <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
        {icono && <Icono nombre={icono} style={{ color: 'var(--qo-cyan)', fontSize: 22 }} />}
        {children}
      </h2>
      {extra}
    </div>
  );
}

const TONO_TAG = { neutro: '', primario: 'cyan', exito: 'green', aviso: 'gold', error: 'red' };

export function Chip({ children, tono = 'neutro', title }) {
  return (
    <span title={title} className={`qo-tag ${TONO_TAG[tono] ?? ''}`}>
      {children}
    </span>
  );
}

export function colorPuntaje(v) {
  if (v == null) return 'var(--qo-muted)';
  if (v >= 80) return 'var(--qo-mint)';
  if (v >= 60) return 'var(--qo-cyan)';
  if (v >= 40) return 'var(--qo-yellow)';
  return '#ffb4ab';
}

export function Puntaje({ valor, tamaño = 34, etiqueta }) {
  return (
    <div className="qo-score">
      <strong style={{ fontSize: tamaño, color: colorPuntaje(valor) }}>{valor ?? '—'}</strong>
      {etiqueta && <span>{etiqueta}</span>}
    </div>
  );
}

export function BarraPuntaje({ etiqueta, valor }) {
  return (
    <div className="qo-skill" style={{ padding: '8px 0' }}>
      <span>
        <span style={{ textTransform: 'capitalize' }}>{etiqueta}</span>
        <small style={{ color: colorPuntaje(valor) }}>{valor ?? '—'} / 100</small>
      </span>
      <div className="qo-progress" style={{ marginTop: 8 }}>
        <span style={{ width: `${valor ?? 0}%` }} />
      </div>
    </div>
  );
}

/** Radar de las cinco dimensiones del Juez IA, en SVG sin dependencias. */
export function Radar({ dimensiones, tamaño = 240 }) {
  const claves = ['arquitectura', 'legibilidad', 'robustez', 'pruebas', 'seguridad'];
  const c = tamaño / 2;
  const r = c - 58;
  const punto = (i, v) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / claves.length;
    return [c + Math.cos(a) * r * (v / 100), c + Math.sin(a) * r * (v / 100)];
  };
  const poligono = claves.map((k, i) => punto(i, dimensiones?.[k] ?? 0).join(',')).join(' ');
  return (
    <svg viewBox={`0 0 ${tamaño} ${tamaño}`} style={{ width: '100%', maxWidth: 280, display: 'block', margin: '0 auto' }} role="img" aria-label="Radar de calidad">
      {[25, 50, 75, 100].map((n) => (
        <polygon key={n} points={claves.map((_, i) => punto(i, n).join(',')).join(' ')} fill="none" stroke="#ffffff14" />
      ))}
      {claves.map((k, i) => {
        const [x, y] = punto(i, 100);
        const [lx, ly] = punto(i, 124);
        return (
          <g key={k}>
            <line x1={c} y1={c} x2={x} y2={y} stroke="#ffffff14" />
            <text x={lx} y={ly} fill="#91a1a6" fontSize="10" textAnchor="middle" dominantBaseline="middle" fontFamily="Consolas, monospace">
              {k}
            </text>
          </g>
        );
      })}
      <polygon points={poligono} fill="rgba(76,215,246,0.18)" stroke="#4cd7f6" strokeWidth="2" />
      {claves.map((k, i) => {
        const [x, y] = punto(i, dimensiones?.[k] ?? 0);
        return <circle key={k} cx={x} cy={y} r="3" fill="#4edea3" />;
      })}
    </svg>
  );
}

export function Aviso({ tipo = 'info', children }) {
  return <div className={`qo-note ${tipo}`}>{children}</div>;
}

export function Boton({ children, onClick, disabled, variante = 'primario', icono, type = 'button', className = '', title }) {
  const clase = { primario: 'primary', secundario: '', fantasma: 'ghost', pequeño: 'small' }[variante] ?? '';
  return (
    <button type={type} onClick={onClick} disabled={disabled} title={title} className={`qo-btn ${clase} ${className}`}>
      {icono && <Icono nombre={icono} />}
      {children}
    </button>
  );
}

export function Filtros({ opciones, valor, onCambio }) {
  return (
    <div className="qo-filters" role="group">
      {opciones.map(([clave, etiqueta]) => (
        <button key={clave} type="button" className="qo-filter" aria-pressed={valor === clave} onClick={() => onCambio(clave)}>
          {etiqueta}
        </button>
      ))}
    </div>
  );
}

export function Cargando({ texto = 'Cargando…' }) {
  return (
    <div className="qo-meta" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '24px 0' }}>
      <span className="qo-pulse" />
      {texto}
    </div>
  );
}

export const fecha = (iso) =>
  iso ? new Date(iso).toLocaleDateString('es-PE', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
