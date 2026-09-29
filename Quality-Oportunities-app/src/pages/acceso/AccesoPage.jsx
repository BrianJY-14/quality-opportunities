import { useEffect, useState } from 'react';

import { estadoIA, salud } from '../../service/api.js';
import fondoLogin from './fondoLogin.js';
import LoginForm from './LoginForm.jsx';
import RegisterForm from './RegisterForm.jsx';

const Sim = ({ id }) => (
  <svg className="icon" aria-hidden="true">
    <use href={`#${id}`} />
  </svg>
);

/**
 * Acceso con el diseño de la maqueta "Demo local": fondo con logos en orbita y tarjeta central.
 * A diferencia de la maqueta, los indicadores de estado son reales: salen de /health y /ia/estado.
 */
export default function AccesoPage({ onLogin }) {
  const [modo, setModo] = useState('login');
  const [pausado, setPausado] = useState(false);
  const [estado, setEstado] = useState({ api: null, ia: null });

  useEffect(() => {
    salud()
      .then((s) => setEstado((e) => ({ ...e, api: s.estado })))
      .catch(() => setEstado((e) => ({ ...e, api: 'sin conexión' })));
    estadoIA()
      .then((i) => setEstado((e) => ({ ...e, ia: i.llm_configurado ? i.modelo : 'modo reglas' })))
      .catch(() => {});
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle('motion-paused', pausado);
    return () => document.documentElement.classList.remove('motion-paused');
  }, [pausado]);

  const enLinea = estado.api === 'ok';

  return (
    <div className="qo-login">
      <div dangerouslySetInnerHTML={{ __html: fondoLogin }} />
      <main className="page">
        <div className="login-shell">
          <section className="login-card" aria-labelledby="login-title">
            <div className="gateway">
              <span className="gateway-tag">● QO_API_v1</span>
              <span className="secure" style={{ color: enLinea ? undefined : '#eec200' }}>
                <Sim id="i-lock" /> {estado.api === null ? 'CONECTANDO…' : enLinea ? 'API EN LÍNEA' : 'API DORMIDA'}
              </span>
            </div>
            <div className="brand" aria-label="Quality Opportunities">
              <svg className="brand-mark" aria-hidden="true">
                <use href="#i-brand" />
              </svg>
              <div>
                <strong>
                  QUALITY <span>OPPORTUNITIES</span>
                </strong>
                <small>APRENDE · CONSTRUYE · DEMUESTRA</small>
              </div>
            </div>
            {modo === 'login' ? (
              <LoginForm onLogin={onLogin} onCrearCuenta={() => setModo('registro')} Sim={Sim} />
            ) : (
              <RegisterForm onLogin={onLogin} onVolver={() => setModo('login')} Sim={Sim} />
            )}
            <div className="card-footer">
              <span>
                <Sim id="i-shield" /> IA: {estado.ia ?? '—'}
              </span>
              <span>{enLinea ? 'BACKEND CONECTADO' : 'EL PLAN GRATUITO TARDA ~1 MIN EN DESPERTAR'}</span>
            </div>
          </section>
          <div className="connection-info">
            <span>
              <Sim id="i-gauge" /> carlos@uni.pe · demo12345
            </span>
            <span>
              <Sim id="i-network" /> representante@ejemplo.pe
            </span>
          </div>
        </div>
      </main>
      <footer className="site-footer">
        <p>
          STATUS: <span className="secure">● {enLinea ? 'NODE_ONLINE' : 'NODE_WAKING'}</span>
        </p>
        <p>QUALITY OPPORTUNITIES · SINERGIA</p>
        <button className="text-button" type="button" aria-pressed={pausado} onClick={() => setPausado((p) => !p)}>
          {pausado ? 'Reanudar animación' : 'Pausar animación'}
        </button>
      </footer>
    </div>
  );
}
