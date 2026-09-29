import { useMemo, useState } from 'react';

/**
 * Grafo de aptitudes en SVG: perfil en el centro, aptitudes en el anillo medio (tamaño segun
 * nivel) y evidencias (credenciales) en el anillo exterior. Pasar el cursor por una aptitud
 * resalta las credenciales que la sustentan: cada afirmacion del CV apunta a su prueba.
 */
export default function GrafoAptitudes({ grafo }) {
  const [foco, setFoco] = useState(null);
  const W = 640;
  const H = 520;
  const cx = W / 2;
  const cy = H / 2;

  const { posiciones, aptitudes, evidencias } = useMemo(() => {
    const apt = grafo.nodos.filter((n) => n.tipo === 'APTITUD');
    const ev = grafo.nodos.filter((n) => n.tipo === 'EVIDENCIA');
    const pos = { perfil: [cx, cy] };
    apt.forEach((n, i) => {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(apt.length, 1);
      pos[n.id] = [cx + Math.cos(a) * 140, cy + Math.sin(a) * 140];
    });
    ev.forEach((n, i) => {
      const a = -Math.PI / 2 + Math.PI / Math.max(ev.length, 1) + (2 * Math.PI * i) / Math.max(ev.length, 1);
      pos[n.id] = [cx + Math.cos(a) * 225, cy + Math.sin(a) * 205];
    });
    return { posiciones: pos, aptitudes: apt, evidencias: ev };
  }, [grafo, cx, cy]);

  const conectados = useMemo(() => {
    if (!foco) return null;
    const s = new Set([foco]);
    grafo.aristas.forEach((e) => {
      if (e.origen === foco) s.add(e.destino);
      if (e.destino === foco) s.add(e.origen);
    });
    return s;
  }, [foco, grafo]);

  const atenuado = (id) => conectados && !conectados.has(id);

  if (aptitudes.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-sm text-on-surface-variant text-center px-6">
        El grafo aparece con la primera credencial: cada aptitud se enlaza con el reto que la demostró.
      </div>
    );
  }

  const corto = (t, n) => (t.length > n ? `${t.slice(0, n - 1)}…` : t);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto select-none" role="img" aria-label="Grafo de aptitudes">
      <defs>
        <radialGradient id="gCentro">
          <stop offset="0%" stopColor="#4cd7f6" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.4" />
        </radialGradient>
      </defs>
      {grafo.aristas.map((e, i) => {
        const [x1, y1] = posiciones[e.origen] ?? [cx, cy];
        const [x2, y2] = posiciones[e.destino] ?? [cx, cy];
        const activa = conectados && conectados.has(e.origen) && conectados.has(e.destino);
        return (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke={activa ? '#4edea3' : '#3d494c'}
            strokeWidth={activa ? 2 : 1}
            opacity={conectados && !activa ? 0.15 : 0.8}
          />
        );
      })}

      {evidencias.map((n) => {
        const [x, y] = posiciones[n.id];
        return (
          <g key={n.id} opacity={atenuado(n.id) ? 0.2 : 1} onMouseEnter={() => setFoco(n.id)} onMouseLeave={() => setFoco(null)}>
            <rect x={x - 62} y={y - 17} width="124" height="34" rx="6" fill="#1c1b1b" stroke="#eec200" strokeWidth="1" />
            <text x={x} y={y - 3} textAnchor="middle" fill="#e5e2e1" fontSize="9.5" fontFamily="Inter">
              {corto(n.etiqueta, 24)}
            </text>
            <text x={x} y={y + 10} textAnchor="middle" fill="#eec200" fontSize="8.5" fontFamily="JetBrains Mono">
              {corto(n.valor ?? '', 24)}
            </text>
          </g>
        );
      })}

      {aptitudes.map((n) => {
        const [x, y] = posiciones[n.id];
        const r = 14 + (n.valor ?? 0) / 7;
        return (
          <g
            key={n.id}
            opacity={atenuado(n.id) ? 0.25 : 1}
            onMouseEnter={() => setFoco(n.id)}
            onMouseLeave={() => setFoco(null)}
            className="cursor-pointer"
          >
            <circle cx={x} cy={y} r={r} fill="rgba(76,215,246,0.15)" stroke="#4cd7f6" strokeWidth="1.5" />
            <text x={x} y={y + 3.5} textAnchor="middle" fill="#4cd7f6" fontSize="10" fontWeight="700" fontFamily="JetBrains Mono">
              {n.valor}
            </text>
            <text x={x} y={y + r + 12} textAnchor="middle" fill="#e5e2e1" fontSize="10.5" fontFamily="Inter">
              {corto(n.etiqueta, 22)}
            </text>
          </g>
        );
      })}

      <circle cx={cx} cy={cy} r="34" fill="url(#gCentro)" />
      <text x={cx} y={cy + 4} textAnchor="middle" fill="#001f26" fontSize="11" fontWeight="800" fontFamily="Plus Jakarta Sans">
        {corto(grafo.nodos[0]?.etiqueta ?? '', 14)}
      </text>
    </svg>
  );
}
