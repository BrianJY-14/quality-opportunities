import { useEffect, useMemo, useState } from 'react';

import { Aviso, Boton, Cargando, Encabezado, Filtros, Icono, Pagina } from '../../components/ui.jsx';
import { miCV, verificarCredencial } from '../../service/api.js';

const ACENTO = { BASICO: '#4edea3', INTERMEDIO: '#4cd7f6', AVANZADO: '#eec200' };
const ICONO = { BASICO: 'school', INTERMEDIO: 'code', AVANZADO: 'verified_user' };

/** Credenciales vigentes con el diseño "Certifications" de la maqueta; la verificacion es real. */
export default function CertificacionesPage() {
  const [cv, setCv] = useState(null);
  const [error, setError] = useState(null);
  const [filtro, setFiltro] = useState('todas');
  const [detalle, setDetalle] = useState(null);

  useEffect(() => {
    miCV().then(setCv).catch(setError);
  }, []);

  const lista = useMemo(
    () => (cv?.evidencias ?? []).filter((e) => filtro === 'todas' || e.dificultad === filtro),
    [cv, filtro],
  );

  const abrir = async (id) => {
    setDetalle({ cargando: true, id });
    try {
      setDetalle(await verificarCredencial(id));
    } catch (e) {
      setDetalle({ error: e.mensaje, id });
    }
  };

  return (
    <Pagina>
      <Encabezado
        eyebrow="CREDENTIALS // VERIFICABLES"
        titulo="Cada logro, con contexto."
        descripcion="Credenciales emitidas al aprobar la batería oficial de un reto. Cualquiera puede verificarlas con su identificador, sin cuenta."
      />
      <div className="qo-toolbar">
        <Filtros
          valor={filtro}
          onCambio={setFiltro}
          opciones={[
            ['todas', 'Todas'],
            ['BASICO', 'Básico'],
            ['INTERMEDIO', 'Intermedio'],
            ['AVANZADO', 'Avanzado'],
          ]}
        />
        {cv && <span className="qo-tag">{cv.evidencias.length} VIGENTES · SHA-256</span>}
      </div>

      {error && <Aviso tipo="error">{error.mensaje}</Aviso>}
      {!cv && !error && <Cargando />}

      <div className="qo-grid">
        {lista.map((e) => (
          <article key={e.identificador_publico} className="qo-card certificate" style={{ '--accent': ACENTO[e.dificultad] ?? 'var(--qo-cyan)' }}>
            <div className="qo-certificate-art">
              <Icono nombre={ICONO[e.dificultad] ?? 'workspace_premium'} />
              <small>{e.organizacion.toUpperCase()}</small>
            </div>
            <div className="qo-eyebrow">{e.dificultad ?? 'RETO'}</div>
            <h3>{e.reto}</h3>
            <div className="qo-tags">
              {(e.aptitudes_reto ?? []).slice(0, 4).map((a) => (
                <span key={a} className="qo-tag">
                  {a}
                </span>
              ))}
            </div>
            <div className="qo-cert-meta">
              <span>{e.identificador_publico}</span>
              <span>Juez IA {e.revision_ia?.puntaje_global ?? '—'}</span>
            </div>
            <div className="qo-actions" style={{ marginTop: 16 }}>
              <Boton variante="secundario" icono="workspace_premium" onClick={() => abrir(e.identificador_publico)}>
                Verificar
              </Boton>
            </div>
          </article>
        ))}
        {cv && !lista.length && <div className="qo-empty">Sin credenciales en esta categoría.</div>}
      </div>

      {detalle && (
        <div className="qo-dialog-fondo" onClick={() => setDetalle(null)} role="presentation">
          <div className="qo-dialog" style={{ display: 'block', position: 'relative' }} onClick={(ev) => ev.stopPropagation()} role="dialog" aria-modal="true">
            <div className="qo-dialog-head">
              <h2>Verificación pública</h2>
              <button className="qo-close" onClick={() => setDetalle(null)} aria-label="Cerrar">
                <Icono nombre="close" />
              </button>
            </div>
            <div className="qo-dialog-body">
              {detalle.cargando && <Cargando />}
              {detalle.error && <Aviso tipo="error">{detalle.error}</Aviso>}
              {detalle.identificador_publico && (
                <>
                  <p>
                    <strong style={{ color: detalle.vigente ? 'var(--qo-mint)' : '#ffb4ab' }}>{detalle.vigente ? 'VIGENTE' : 'REVOCADA'}</strong> ·{' '}
                    {detalle.identificador_publico}
                  </p>
                  <h3>{detalle.reto}</h3>
                  <p>
                    Emitida a <strong>{detalle.estudiante}</strong> por <strong>{detalle.emisor}</strong>.
                  </p>
                  <p>{detalle.criterios_aceptacion}</p>
                  <pre>{`huella_contenido: ${detalle.huella_contenido}\nversion_evaluador: ${detalle.version_evaluador}\ncommit: ${detalle.commit}`}</pre>
                  {detalle.revocacion && <Aviso tipo="error">Revocada: {detalle.revocacion.motivo}</Aviso>}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </Pagina>
  );
}
