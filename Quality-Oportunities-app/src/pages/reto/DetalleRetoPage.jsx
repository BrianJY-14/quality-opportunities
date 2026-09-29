import { useEffect, useState } from 'react';

import { Aviso, Boton, Cargando, Chip, Icono, Pagina, Tarjeta, Titulo } from '../../components/ui.jsx';
import { useAuthContext } from '../../context/AuthContext.jsx';
import { verReto } from '../../service/api.js';

const XP_BASE = { BASICO: 100, INTERMEDIO: 180, AVANZADO: 300 };
const CATEGORIA = { FUNCIONAL: 'Funcional', CASO_LIMITE: 'Caso límite', RENDIMIENTO: 'Rendimiento' };

/** Detalle real del reto: todo sale de GET /retos/{id}. */
export default function DetalleRetoPage({ retoId, onIniciar, onVolver }) {
  const { usuario } = useAuthContext();
  const [reto, setReto] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!retoId) return;
    verReto(retoId).then(setReto).catch(setError);
  }, [retoId]);

  return (
    <Pagina>
      <Boton variante="fantasma" icono="arrow_back" onClick={onVolver}>
        Volver a retos
      </Boton>

      {!retoId && <Aviso>Selecciona un reto del catálogo.</Aviso>}
      {error && <Aviso tipo="error">{error.mensaje}</Aviso>}
      {retoId && !reto && !error && <Cargando />}

      {reto && (
        <>
          <div className="qo-card qo-profile" style={{ margin: '18px 0 24px' }}>
            <div className="qo-meta">
              {reto.organizacion.nombre.toUpperCase()} // {reto.dificultad ?? 'SIN NIVEL'} · {XP_BASE[reto.dificultad] ?? 150} XP BASE
            </div>
            <h1 style={{ fontSize: 'clamp(28px,3.4vw,40px)', letterSpacing: '-.04em', margin: '10px 0 16px', fontWeight: 700 }}>{reto.titulo}</h1>
            <div className="qo-tags" style={{ marginTop: 0 }}>
              <Chip tono={reto.estado === 'PUBLICADO' ? 'exito' : 'neutro'}>{reto.estado === 'PUBLICADO' ? 'Abierto' : reto.estado}</Chip>
              {reto.aptitudes.map((a) => (
                <Chip key={a} tono="primario">
                  {a}
                </Chip>
              ))}
            </div>
          </div>

          <div className="qo-two">
            <div className="qo-stack">
              <Tarjeta>
                <Titulo icono="description">Problema</Titulo>
                <p style={{ whiteSpace: 'pre-line', margin: 0 }}>{reto.descripcion_publica}</p>
              </Tarjeta>
              <Tarjeta>
                <Titulo icono="task_alt" extra={<Chip tono="primario">{reto.pruebas_obligatorias} obligatorias</Chip>}>
                  Pruebas oficiales
                </Titulo>
                <div className="qo-list">
                  {reto.pruebas.map((p) => (
                    <div key={p.id} className="qo-row">
                      <Icono nombre={p.obligatoria ? 'check_circle' : 'radio_button_unchecked'} style={{ color: p.obligatoria ? 'var(--qo-cyan)' : '#7f8f94' }} />
                      <div style={{ flex: 1 }}>
                        <h3>{p.nombre}</h3>
                        <p>{p.condicion_aprobacion}</p>
                        <div className="qo-tags" style={{ marginTop: 10 }}>
                          <span className="qo-tag">{CATEGORIA[p.categoria] ?? p.categoria}</span>
                          {p.tiene_codigo && <span className="qo-tag green">ejecutable</span>}
                          {p.limite_ejecucion_ms && <span className="qo-tag">{p.limite_ejecucion_ms} ms</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </Tarjeta>
            </div>

            <div className="qo-stack">
              <Tarjeta>
                <Titulo icono="rocket_launch">Resolver</Titulo>
                <p style={{ marginTop: 0 }}>{reto.criterios_aceptacion}</p>
                {usuario?.tiene_perfil_estudiante ? (
                  <Boton icono="code" onClick={onIniciar} disabled={reto.estado !== 'PUBLICADO'} className="w-full">
                    Ir a mi espacio de trabajo
                  </Boton>
                ) : (
                  <Aviso>Se necesita una cuenta con perfil de estudiante para participar.</Aviso>
                )}
              </Tarjeta>
              <Tarjeta>
                <Titulo icono="route">Cómo se evalúa</Titulo>
                <div className="qo-timeline">
                  {[
                    ['Editor y Tutor IA', 'Proyecto inicial en el navegador; el tutor da pistas, no soluciones.'],
                    ['Entrega congelada', 'Al enviar se guarda una copia del proyecto con su huella SHA-256.'],
                    ['Pruebas oficiales', 'Deciden el dictamen; aprobar emite una credencial verificable.'],
                    ['Juez IA', 'Revisa arquitectura, legibilidad, robustez, pruebas y seguridad.'],
                    ['Defensa técnica', 'Preguntas sobre las decisiones del código; suma XP al ranking.'],
                  ].map(([t, d]) => (
                    <article key={t}>
                      <h3>{t}</h3>
                      <p>{d}</p>
                    </article>
                  ))}
                </div>
              </Tarjeta>
            </div>
          </div>
        </>
      )}
    </Pagina>
  );
}
