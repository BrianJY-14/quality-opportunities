import { useCallback, useEffect, useState } from 'react';

import GrafoAptitudes from '../../components/GrafoAptitudes.jsx';
import { Aviso, BarraPuntaje, Boton, Cargando, Chip, Encabezado, Icono, Pagina, Radar, Tarjeta, Titulo, colorPuntaje, fecha } from '../../components/ui.jsx';
import { actualizarPerfil, cvPublico, generarResumenCV, miCV } from '../../service/api.js';
import { InsigniaRango } from '../ranking/RankingPage.jsx';

/**
 * CV dinamico con el diseño "Curriculum" de la maqueta. Sin `nombrePublico` muestra el propio
 * (con acciones); con el, el CV publico. Nada de lo que se ve lo escribe el estudiante: todo sale
 * de credenciales vigentes, del Juez IA y de las defensas.
 */
export default function CVPage({ nombrePublico }) {
  const propio = !nombrePublico;
  const [cv, setCv] = useState(null);
  const [error, setError] = useState(null);
  const [generando, setGenerando] = useState(false);
  const [aviso, setAviso] = useState(null);

  const cargar = useCallback(() => {
    setError(null);
    (propio ? miCV() : cvPublico(nombrePublico)).then(setCv).catch(setError);
  }, [propio, nombrePublico]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const resumir = async () => {
    setGenerando(true);
    setAviso(null);
    try {
      const r = await generarResumenCV();
      setCv((c) => ({ ...c, ...r }));
    } catch (e) {
      setAviso({ tipo: 'error', texto: e.mensaje });
    } finally {
      setGenerando(false);
    }
  };

  const alternarVisibilidad = async () => {
    const visibilidad = cv.visibilidad === 'PUBLICO' ? 'PRIVADO' : 'PUBLICO';
    await actualizarPerfil({ visibilidad });
    setCv((c) => ({ ...c, visibilidad }));
  };

  const copiar = async () => {
    const enlace = `${window.location.origin}${window.location.pathname}#/perfil/${encodeURIComponent(cv.nombre_publico)}`;
    try {
      await navigator.clipboard.writeText(enlace);
      setAviso({ tipo: 'ok', texto: 'Enlace público copiado.' });
    } catch {
      setAviso({ tipo: 'info', texto: enlace });
    }
  };

  if (error) {
    return (
      <Pagina>
        <Aviso tipo="error">{error.mensaje}</Aviso>
      </Pagina>
    );
  }
  if (!cv) {
    return (
      <Pagina>
        <Cargando texto="Construyendo el CV desde la evidencia…" />
      </Pagina>
    );
  }

  const r = cv.rango;
  const m = cv.metricas;

  return (
    <Pagina>
      <Encabezado
        eyebrow={propio ? 'PROOF OF WORK // CV DINÁMICO' : 'PROOF OF WORK // PERFIL PÚBLICO'}
        titulo="El aprendizaje, con evidencia."
        descripcion="Credenciales verificables, calidad medida por el Juez IA y defensas técnicas, reunidas en un currículum que se puede explorar."
        acciones={
          propio && (
            <>
              <Boton variante="secundario" icono={cv.visibilidad === 'PUBLICO' ? 'visibility_off' : 'visibility'} onClick={alternarVisibilidad}>
                {cv.visibilidad === 'PUBLICO' ? 'Hacer privado' : 'Hacer público'}
              </Boton>
              <Boton icono="link" onClick={copiar} disabled={cv.visibilidad !== 'PUBLICO'}>
                Enlace público
              </Boton>
            </>
          )
        }
      />

      {aviso && (
        <div style={{ marginBottom: 20 }}>
          <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>
        </div>
      )}

      <div className="qo-two">
        <div className="qo-stack">
          <section className="qo-card qo-profile">
            <div className="qo-profile-top">
              <span className="qo-avatar">{cv.nombre_publico.charAt(0).toUpperCase()}</span>
              <div>
                <h2>{cv.nombre_publico}</h2>
                <div className="qo-role">{[cv.carrera, cv.universidad, cv.ciclo ? `${cv.ciclo}.º ciclo` : null].filter(Boolean).join(' · ')}</div>
                <div className="qo-tags" style={{ marginTop: 12 }}>
                  <InsigniaRango rango={r} />
                  <Chip tono="aviso">{r.xp} XP</Chip>
                  {propio && <Chip tono={cv.visibilidad === 'PUBLICO' ? 'exito' : 'neutro'}>{cv.visibilidad}</Chip>}
                </div>
              </div>
            </div>
            {cv.resumen_ia ? (
              <>
                <p style={{ color: 'var(--qo-text)' }}>{cv.resumen_ia}</p>
                <span className="qo-meta">Redactado por IA solo con la evidencia verificada · {fecha(cv.momento_resumen)}</span>
              </>
            ) : (
              <p>{cv.biografia || (cv.evidencias.length ? 'El resumen profesional aún no se generó.' : 'Aparecerá cuando el perfil tenga su primera credencial.')}</p>
            )}
            {propio && cv.evidencias.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <Boton variante="fantasma" icono="auto_awesome" onClick={resumir} disabled={generando}>
                  {generando ? 'Redactando…' : cv.resumen_ia ? 'Regenerar resumen con IA' : 'Generar resumen con IA'}
                </Boton>
              </div>
            )}
            <div className="qo-stats">
              <div className="qo-stat">
                <strong style={{ color: 'var(--qo-mint)' }}>{m.credenciales_vigentes}</strong>
                <span>Credenciales vigentes</span>
              </div>
              <div className="qo-stat">
                <strong>{m.retos_intentados}</strong>
                <span>Retos intentados</span>
              </div>
              <div className="qo-stat">
                <strong style={{ color: 'var(--qo-yellow)' }}>{m.organizaciones}</strong>
                <span>Organizaciones</span>
              </div>
            </div>
            <div className="qo-meta" style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
              <span>{r.nombre}</span>
              <span>{r.siguiente ? `${r.xp_siguiente - r.xp} XP para ${r.siguiente}` : 'Rango máximo'}</span>
            </div>
            <div className="qo-progress">
              <span style={{ width: `${r.progreso_pct}%` }} />
            </div>
          </section>

          <Tarjeta>
            <Titulo icono="hub">Grafo de aptitudes técnicas</Titulo>
            <GrafoAptitudes grafo={cv.grafo} />
            <p className="qo-meta" style={{ marginBottom: 0 }}>
              Pasar el cursor por una aptitud resalta las credenciales que la sustentan. El número es el nivel (0-100), con
              valor marginal decreciente al repetir retos parecidos.
            </p>
          </Tarjeta>

          <Tarjeta>
            <Titulo icono="verified">Proof-of-Work verificable</Titulo>
            {cv.evidencias.map((e) => (
              <div key={e.identificador_publico} className="qo-evidence" style={{ display: 'flex', gap: 16, justifyContent: 'space-between', flexWrap: 'wrap' }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <h3>{e.reto}</h3>
                  <div className="qo-meta">
                    {e.organizacion} · emitida {fecha(e.momento_emision)} · {e.dificultad ?? 'SIN NIVEL'}
                  </div>
                  <div className="qo-meta" style={{ overflowWrap: 'anywhere' }}>
                    {e.identificador_publico}
                    {e.huella_proyecto ? ` · sha256 ${e.huella_proyecto.slice(0, 16)}…` : ''} · evaluador {e.version_evaluador}
                  </div>
                </div>
                <div className="qo-actions" style={{ gap: 20 }}>
                  <div className="qo-score">
                    <strong style={{ fontSize: 22, color: colorPuntaje(e.revision_ia?.puntaje_global) }}>{e.revision_ia?.puntaje_global ?? '—'}</strong>
                    <span>Juez IA</span>
                  </div>
                  <div className="qo-score">
                    <strong style={{ fontSize: 22, color: colorPuntaje(e.defensa?.puntaje) }}>{e.defensa?.puntaje ?? '—'}</strong>
                    <span>Defensa</span>
                  </div>
                  <div className="qo-score">
                    <strong style={{ fontSize: 22, color: 'var(--qo-yellow)' }}>+{e.xp}</strong>
                    <span>XP</span>
                  </div>
                </div>
              </div>
            ))}
            {!cv.evidencias.length && <p style={{ margin: 0 }}>Sin credenciales vigentes. Resolver un reto del catálogo abre la primera.</p>}
          </Tarjeta>
        </div>

        <div className="qo-stack">
          <Tarjeta>
            <h2>Mapa de habilidades</h2>
            <p className="qo-meta" style={{ marginTop: -8 }}>
              Niveles derivados de credenciales vigentes. Cada uno apunta a su evidencia.
            </p>
            {cv.aptitudes.slice(0, 10).map((a) => (
              <BarraPuntaje key={a.nombre} etiqueta={`${a.nombre} · ${a.evidencias.length} evid.`} valor={a.nivel} />
            ))}
            {!cv.aptitudes.length && <p>Sin aptitudes verificadas todavía.</p>}
          </Tarjeta>
          <Tarjeta>
            <h2>Calidad de ingeniería</h2>
            {Object.keys(cv.dimensiones).length ? (
              <>
                <Radar dimensiones={cv.dimensiones} />
                {Object.entries(cv.dimensiones).map(([k, v]) => (
                  <BarraPuntaje key={k} etiqueta={k} valor={v} />
                ))}
              </>
            ) : (
              <p>Sin revisiones del Juez IA todavía.</p>
            )}
          </Tarjeta>
          <div className="qo-note">
            <Icono nombre="info" style={{ fontSize: 16, verticalAlign: -3, marginRight: 6 }} />
            Promedio Juez IA: {m.promedio_juez_ia ?? '—'} · Promedio defensa: {m.promedio_defensa ?? '—'}. Revocar una credencial la
            retira de este CV y del ranking en el acto.
          </div>
        </div>
      </div>
    </Pagina>
  );
}
