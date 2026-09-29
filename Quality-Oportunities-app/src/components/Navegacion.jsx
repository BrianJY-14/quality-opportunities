import { useEffect, useState } from 'react';

import { useAuthContext } from '../context/AuthContext.jsx';
import { estadoIA } from '../service/api.js';
import { Icono } from './ui.jsx';

/**
 * Cabecera comun (qo-header). La pestaña de organizacion solo aparece si la cuenta representa a
 * alguna: no hay rol global, la misma persona puede ser estudiante y representante a la vez.
 */
export default function Navegacion({ ruta, onNavegar, onSalir }) {
  const { usuario } = useAuthContext();
  const [ia, setIa] = useState(null);

  useEffect(() => {
    estadoIA().then(setIa).catch(() => setIa(null));
  }, []);

  const pestañas = [
    ['catalogo', 'Retos'],
    ...(usuario?.tiene_perfil_estudiante ? [['cv', 'Mi CV'], ['certificaciones', 'Certificaciones']] : []),
    ['ranking', 'Ranking'],
    ...(usuario?.representaciones?.length ? [['organizacion', 'Organización']] : []),
  ];
  const activa = ['detalle', 'espacio', 'resultado'].includes(ruta) ? 'catalogo' : ruta;
  const inicial = (usuario?.nombre ?? '?').charAt(0).toUpperCase();

  const ir = (e, clave) => {
    e.preventDefault();
    onNavegar(clave);
  };

  return (
    <header className="qo-header">
      <div className="qo-header-inner">
        <button type="button" className="qo-wordmark" onClick={() => onNavegar('catalogo')}>
          <span>
            <Icono nombre="hub" />
          </span>
          <span>QUALITY OPPORTUNITIES</span>
        </button>

        <nav className="qo-nav" aria-label="Navegación principal">
          {pestañas.map(([clave, etiqueta]) => (
            <a key={clave} href={`#${clave}`} onClick={(e) => ir(e, clave)} aria-current={activa === clave ? 'page' : undefined}>
              {etiqueta}
            </a>
          ))}
        </nav>

        <div className="qo-actions" style={{ gap: 14 }}>
          {ia && (
            <span
              className={`qo-tag ${ia.llm_configurado ? 'green' : ''}`}
              title={ia.llm_configurado ? `Modelo: ${ia.modelo}` : 'Sin LLM configurado: funciones de IA en modo reglas'}
            >
              <Icono nombre="neurology" style={{ fontSize: 15 }} />
              {ia.llm_configurado ? 'IA ACTIVA' : 'IA · REGLAS'}
            </span>
          )}
          {usuario ? (
            <>
              <button
                type="button"
                className="qo-user"
                onClick={() => onNavegar(usuario.tiene_perfil_estudiante ? 'cv' : 'catalogo')}
                title="Ver mi CV"
              >
                <span style={{ color: 'var(--qo-muted)' }}>{usuario.nombre}</span>
                <span className="qo-avatar">{inicial}</span>
              </button>
              <button type="button" className="qo-close" onClick={onSalir} title="Cerrar sesión" aria-label="Cerrar sesión">
                <Icono nombre="logout" style={{ fontSize: 19 }} />
              </button>
            </>
          ) : (
            <button type="button" className="qo-btn small" onClick={() => onNavegar('acceso')}>
              <Icono nombre="login" />
              Ingresar
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
