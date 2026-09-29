import { useEffect, useState } from 'react';

import Navegacion from './components/Navegacion.jsx';
import { AuthProvider, useAuthContext } from './context/AuthContext.jsx';
import AccesoPage from './pages/acceso/AccesoPage.jsx';
import CatalogoPage from './pages/catalogo/CatalogoPage.jsx';
import CertificacionesPage from './pages/cv/CertificacionesPage.jsx';
import CVPage from './pages/cv/CVPage.jsx';
import EspacioTrabajoPage from './pages/espacio/EspacioTrabajoPage.jsx';
import OrganizacionPage from './pages/organizacion/OrganizacionPage.jsx';
import RankingPage from './pages/ranking/RankingPage.jsx';
import ResultadoPage from './pages/resultado/ResultadoPage.jsx';
import DetalleRetoPage from './pages/reto/DetalleRetoPage.jsx';

/**
 * Enlaces publicos que no requieren sesion:
 *   #/perfil/<nombre_publico>   CV dinamico publico
 *   #/ranking                   leaderboard
 * El resto de pantallas se navega con estado, como antes.
 */
function rutaDelHash() {
  const partes = window.location.hash.replace(/^#\/?/, '').split('/');
  if (partes[0] === 'perfil' && partes[1]) return { ruta: 'cv', perfil: decodeURIComponent(partes[1]) };
  if (partes[0] === 'ranking') return { ruta: 'ranking', perfil: null };
  return null;
}

function Contenido() {
  const { autenticado, logout } = useAuthContext();
  const inicial = rutaDelHash();
  const [route, setRoute] = useState(inicial?.ruta ?? 'acceso');
  const [perfilVisto, setPerfilVisto] = useState(inicial?.perfil ?? null);
  const [retoSeleccionado, setRetoSeleccionado] = useState(null);
  // El envio devuelve el identificador de la evaluacion, y la pantalla de resultado lo necesita
  // para consultar su estado.
  const [evaluacion, setEvaluacion] = useState({ id: null, tituloReto: null });

  // Una sesion recuperada al recargar salta el login.
  useEffect(() => {
    if (autenticado && route === 'acceso') setRoute('catalogo');
  }, [autenticado, route]);

  const navigate = (next, payload) => {
    setRoute(next);
    if (next === 'cv') setPerfilVisto(payload ?? null);
    else if (payload) setRetoSeleccionado(payload);
    if (next !== 'cv' && next !== 'ranking' && window.location.hash) {
      window.history.replaceState(null, '', window.location.pathname);
    }
    window.scrollTo(0, 0);
  };

  const alEnviar = (evaluacionId, tituloReto) => {
    setEvaluacion({ id: evaluacionId, tituloReto: tituloReto ?? retoSeleccionado?.titulo ?? null });
    setRoute('resultado');
  };

  const salir = () => {
    logout();
    setRoute('acceso');
  };

  const publica = route === 'cv' && perfilVisto;
  const conBarra = route !== 'acceso' && (autenticado || route === 'ranking' || publica);

  const renderPage = () => {
    switch (route) {
      case 'acceso':
        return <AccesoPage onLogin={() => navigate('catalogo')} />;
      case 'catalogo':
        return <CatalogoPage onSelectReto={(reto) => navigate('detalle', reto)} />;
      case 'detalle':
        return (
          <DetalleRetoPage
            retoId={retoSeleccionado?.id}
            onIniciar={() => navigate('espacio')}
            onVolver={() => navigate('catalogo')}
          />
        );
      case 'espacio':
        return (
          <EspacioTrabajoPage retoId={retoSeleccionado?.id} onEnviar={alEnviar} onVolver={() => navigate('detalle')} />
        );
      case 'resultado':
        return (
          <ResultadoPage
            evaluacionId={evaluacion.id}
            tituloReto={evaluacion.tituloReto}
            onVolver={() => navigate('catalogo')}
            onVerCV={() => navigate('cv')}
          />
        );
      case 'ranking':
        return <RankingPage onVerPerfil={(nombre) => navigate('cv', nombre)} />;
      case 'cv':
        return <CVPage nombrePublico={perfilVisto} />;
      case 'organizacion':
        return <OrganizacionPage />;
      case 'certificaciones':
        return <CertificacionesPage />;
      default:
        return <AccesoPage onLogin={() => navigate('catalogo')} />;
    }
  };

  return (
    <>
      <LuzPuntero />
      {conBarra && <Navegacion ruta={route} onNavegar={(r) => navigate(r)} onSalir={salir} />}
      {renderPage()}
    </>
  );
}

/** Halo tenue que sigue al puntero, como en la maqueta. Se desactiva en pantallas tactiles por CSS. */
function LuzPuntero() {
  useEffect(() => {
    const luz = document.getElementById('qo-glow');
    if (!luz) return undefined;
    const mover = (e) => {
      luz.style.transform = `translate(${e.clientX - 210}px, ${e.clientY - 210}px)`;
      luz.style.opacity = '1';
    };
    const salir = () => {
      luz.style.opacity = '0';
    };
    window.addEventListener('pointermove', mover);
    document.addEventListener('pointerleave', salir);
    return () => {
      window.removeEventListener('pointermove', mover);
      document.removeEventListener('pointerleave', salir);
    };
  }, []);
  return <div id="qo-glow" aria-hidden="true" />;
}

export default function App() {
  return (
    <AuthProvider>
      <Contenido />
    </AuthProvider>
  );
}
