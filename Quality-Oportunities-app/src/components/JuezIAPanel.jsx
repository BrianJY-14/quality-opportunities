import { useState } from 'react';

import { Aviso, BarraPuntaje, Boton, Chip, Icono, Puntaje, Radar, Tarjeta, Titulo } from './ui.jsx';

/**
 * Informe del Juez IA. Separa lo medido (analisis estatico) de lo opinado (modelo) y recuerda que
 * no forma parte del dictamen: aprobar depende solo de las pruebas oficiales.
 */
export default function JuezIAPanel({ revision, onReintentar }) {
  const [reintentando, setReintentando] = useState(false);
  const [errorReintento, setErrorReintento] = useState(null);
  if (!revision) return null;
  if (revision.estado === 'SIN_CODIGO') {
    return (
      <Tarjeta>
        <Titulo icono="gavel">Juez IA</Titulo>
        <p style={{ margin: 0 }}>{revision.resumen}</p>
      </Tarjeta>
    );
  }

  const estatico = revision.analisis_estatico ?? {};
  const m = estatico.metricas ?? {};

  return (
    <Tarjeta className="qo-profile">
      <Titulo
        icono="gavel"
        extra={
          <Chip tono={revision.estado === 'COMPLETADA' ? 'exito' : 'neutro'} title={revision.version_instrucciones}>
            {revision.modelo}
          </Chip>
        }
      >
        Juez IA de arquitectura
      </Titulo>

      {revision.estado === 'SOLO_ESTATICA' && onReintentar && (
        <div className="qo-actions" style={{ marginBottom: 16 }}>
          <Boton
            variante="secundario"
            icono="auto_awesome"
            disabled={reintentando}
            onClick={async () => {
              setReintentando(true);
              setErrorReintento(null);
              try {
                await onReintentar();
              } catch (e) {
                setErrorReintento(e?.mensaje ?? 'No se pudo contactar al modelo.');
              } finally {
                setReintentando(false);
              }
            }}
          >
            {reintentando ? 'Consultando al modelo…' : 'Reintentar revisión con IA'}
          </Boton>
          {errorReintento && <Aviso tipo="error">{errorReintento}</Aviso>}
        </div>
      )}

      <div className="qo-two" style={{ gridTemplateColumns: 'minmax(220px, 280px) minmax(0, 1fr)', alignItems: 'center' }}>
        <div>
          <Radar dimensiones={revision.dimensiones} />
          <Puntaje valor={revision.puntaje_global} tamaño={40} etiqueta="Puntaje de calidad" />
        </div>
        <div>
          {Object.entries(revision.dimensiones ?? {}).map(([k, v]) => (
            <BarraPuntaje key={k} etiqueta={k} valor={v} />
          ))}
          {revision.resumen && <p style={{ marginBottom: 0 }}>{revision.resumen}</p>}
        </div>
      </div>

      <div className="qo-grid dos" style={{ marginTop: 22 }}>
        {revision.fortalezas?.length > 0 && (
          <div>
            <div className="qo-eyebrow">Fortalezas</div>
            {revision.fortalezas.map((f, i) => (
              <p key={i} style={{ display: 'flex', gap: 8, margin: '10px 0', fontSize: 14 }}>
                <Icono nombre="check" style={{ color: 'var(--qo-mint)', fontSize: 18 }} />
                {f}
              </p>
            ))}
          </div>
        )}
        {revision.mejoras?.length > 0 && (
          <div>
            <div className="qo-eyebrow" style={{ color: 'var(--qo-yellow)' }}>
              Mejoras sugeridas
            </div>
            {revision.mejoras.map((f, i) => (
              <p key={i} style={{ display: 'flex', gap: 8, margin: '10px 0', fontSize: 14 }}>
                <Icono nombre="arrow_right" style={{ color: 'var(--qo-yellow)', fontSize: 18 }} />
                {f}
              </p>
            ))}
          </div>
        )}
      </div>

      {revision.aptitudes?.length > 0 && (
        <div className="qo-tags">
          {revision.aptitudes.map((a) => (
            <Chip key={a.nombre} tono="primario" title={a.evidencia}>
              {a.nombre}
            </Chip>
          ))}
        </div>
      )}

      <div className="qo-cert-meta" style={{ flexWrap: 'wrap', justifyContent: 'flex-start', gap: '6px 18px' }}>
        <span>Medido sin modelo:</span>
        <span>{m.lineas_codigo ?? 0} líneas</span>
        <span>{m.funciones ?? 0} funciones</span>
        <span>complejidad media {m.complejidad_media ?? '—'}</span>
        <span>reglas de riesgo {estatico.puntaje_reglas ?? '—'}/100</span>
        <span>{m.tiene_pruebas ? 'con pruebas propias' : 'sin pruebas propias'}</span>
      </div>
      <p className="qo-meta" style={{ marginBottom: 0 }}>
        La revisión no cambia el dictamen: aprobar depende solo de las pruebas oficiales del reto.
      </p>
    </Tarjeta>
  );
}
