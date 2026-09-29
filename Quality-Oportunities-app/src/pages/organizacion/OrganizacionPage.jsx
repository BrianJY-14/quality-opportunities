import { useCallback, useEffect, useState } from 'react';

import { Aviso, Boton, Cargando, Chip, Encabezado, Pagina, Tarjeta, Titulo, fecha } from '../../components/ui.jsx';
import { useAuthContext } from '../../context/AuthContext.jsx';
import {
  cerrarReto,
  corregirBorrador,
  enviarSolicitud,
  publicarReto,
  retosDeOrganizacion,
  solicitudesDeOrganizacion,
  verBorrador,
  verSolicitud,
} from '../../service/api.js';

const EJEMPLO = `Issue interno #4821 - Cobros duplicados en campañas
En picos de campaña el app movil reintenta POST /pagos cuando la red falla. El servicio
payments-core (10.20.3.14) no deduplica y se registran cargos dobles.
Credenciales de staging: api_key=sk_live_51Hx9EXAMPLE  contacto: sre-pagos@empresa.pe
Necesitamos que cada pago se aplique una sola vez aunque llegue repetido, y detectar cuando
el mismo id llega con otro monto.`;

const ESTADO_TONO = { BORRADOR: 'aviso', PUBLICADO: 'exito', CERRADO: 'neutro' };

/**
 * Portal de la organizacion: el representante envia un issue privado, el AI Scoper lo sanea y
 * propone un reto en borrador, y una persona lo revisa y publica (RN-ING-02).
 */
export default function OrganizacionPage() {
  const { usuario } = useAuthContext();
  const reps = usuario?.representaciones ?? [];
  const [orgId, setOrgId] = useState(reps[0]?.organizacion_id ?? null);
  const [retos, setRetos] = useState([]);
  const [solicitudes, setSolicitudes] = useState([]);
  const [titulo, setTitulo] = useState('');
  const [contenido, setContenido] = useState('');
  const [procesando, setProcesando] = useState(null);
  const [borrador, setBorrador] = useState(null);
  const [aviso, setAviso] = useState(null);

  const recargar = useCallback(() => {
    if (!orgId) return;
    retosDeOrganizacion(orgId).then(setRetos).catch(() => {});
    solicitudesDeOrganizacion(orgId).then(setSolicitudes).catch(() => {});
  }, [orgId]);

  useEffect(recargar, [recargar]);

  const abrir = async (retoId) => {
    setAviso(null);
    setBorrador(await verBorrador(retoId));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const enviar = async (e) => {
    e.preventDefault();
    setAviso(null);
    try {
      let s = await enviarSolicitud(orgId, titulo, contenido);
      setProcesando(s);
      for (let i = 0; i < 90 && ['RECIBIDA', 'PROCESANDO'].includes(s.estado_preparacion); i += 1) {
        await new Promise((r) => setTimeout(r, 1500));
        s = await verSolicitud(s.id);
        setProcesando(s);
      }
      recargar();
      if (s.reto_borrador_id) {
        await abrir(s.reto_borrador_id);
        setTitulo('');
        setContenido('');
      } else {
        setAviso({ tipo: 'error', texto: s.detalle_error ?? 'La preparación no terminó.' });
      }
    } catch (err) {
      setAviso({ tipo: 'error', texto: err.mensaje });
    } finally {
      setProcesando(null);
    }
  };

  if (!reps.length) {
    return (
      <Pagina>
        <Aviso>Esta cuenta no representa a ninguna organización.</Aviso>
      </Pagina>
    );
  }

  return (
    <Pagina>
      <Encabezado
        eyebrow="PORTAL // AI PEDAGOGICAL SCOPER"
        titulo="Del issue privado al reto publicado."
        descripcion="El Scoper sanea secretos, IPs y correos antes de enviar el material al modelo, redacta el enunciado, propone pruebas en pytest y un proyecto inicial. Nada se publica sin revisión humana."
        acciones={
          reps.length > 1 && (
          <select
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            className="qo-search"
          >
            {reps.map((r) => (
              <option key={r.organizacion_id} value={r.organizacion_id}>
                {r.organizacion}
              </option>
            ))}
          </select>
          )
        }
      />

      <div className="qo-stack">
      {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}

      {borrador && <EditorBorrador borrador={borrador} setBorrador={setBorrador} onCambio={recargar} setAviso={setAviso} />}

      <div className="qo-grid dos" style={{ alignItems: 'start' }}>
        <Tarjeta>
          <Titulo icono="upload_file">Enviar issue al AI Scoper</Titulo>
          <form onSubmit={enviar} className="qo-stack" style={{ gap: 12 }}>
            <input
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              required
              minLength={4}
              placeholder="Título interno del issue"
              className="qo-input"
            />
            <textarea
              value={contenido}
              onChange={(e) => setContenido(e.target.value)}
              required
              rows={9}
              placeholder="Pega el issue tal cual. Los datos sensibles se redactan antes de salir de la plataforma."
              className="qo-textarea" style={{ fontFamily: 'var(--qo-mono)', fontSize: 13 }}
            />
            <div className="qo-actions">
              <Boton type="submit" icono="auto_awesome" disabled={!!procesando || !orgId}>
                {procesando ? `Preparando… (${procesando.estado_preparacion})` : 'Preparar reto con IA'}
              </Boton>
              <Boton
                variante="fantasma"
                icono="science"
                onClick={() => {
                  setTitulo('Cobros duplicados por reintentos');
                  setContenido(EJEMPLO);
                }}
              >
                Usar ejemplo con secretos
              </Boton>
            </div>
          </form>
        </Tarjeta>

        <div className="qo-stack">
          <Tarjeta>
            <Titulo icono="list_alt">Retos de la organización</Titulo>
            <div className="qo-list">
              {retos.map((r) => (
                <div key={r.id} className="qo-row" style={{ alignItems: 'center' }}>
                  <div style={{ minWidth: 0 }}>
                    <h3>{r.titulo}</h3>
                    <span className="qo-meta">
                      {r.pruebas_obligatorias}/{r.pruebas_totales} obligatorias {r.dificultad ? `· ${r.dificultad}` : ''}
                    </span>
                  </div>
                  <div className="qo-actions">
                    <Chip tono={ESTADO_TONO[r.estado]}>{r.estado}</Chip>
                    <Boton variante="fantasma" icono="open_in_new" onClick={() => abrir(r.id)} />
                  </div>
                </div>
              ))}
              {!retos.length && <Cargando />}
            </div>
          </Tarjeta>
          <Tarjeta>
            <Titulo icono="history">Solicitudes al Scoper</Titulo>
            <div className="qo-list" style={{ maxHeight: 300, overflowY: 'auto' }}>
              {solicitudes.map((s) => (
                <div key={s.id} className="qo-row" style={{ flexDirection: 'column', gap: 4 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, width: '100%' }}>
                    <h3>{s.titulo_original}</h3>
                    <Chip tono={s.estado_preparacion === 'LISTA' ? 'exito' : 'aviso'}>{s.estado_preparacion}</Chip>
                  </div>
                  <span className="qo-meta">
                    {fecha(s.momento_recepcion)} · {s.modelo_ia ?? '—'}
                  </span>
                </div>
              ))}
              {!solicitudes.length && <p>Sin solicitudes aún.</p>}
            </div>
          </Tarjeta>
        </div>
      </div>
      </div>
    </Pagina>
  );
}

function EditorBorrador({ borrador, setBorrador, onCambio, setAviso }) {
  const esBorrador = borrador.estado === 'BORRADOR';
  const [form, setForm] = useState({});
  const [ocupado, setOcupado] = useState(false);
  const [abierta, setAbierta] = useState(null);

  useEffect(() => {
    setForm({
      titulo: borrador.titulo,
      descripcion_publica: borrador.descripcion_publica,
      criterios_aceptacion: borrador.criterios_aceptacion,
      dificultad: borrador.dificultad ?? 'INTERMEDIO',
      aptitudes: (borrador.aptitudes ?? []).join(', '),
    });
  }, [borrador]);

  const accion = async (fn, ok) => {
    setOcupado(true);
    try {
      const r = await fn();
      if (r) setBorrador(await verBorrador(borrador.id));
      setAviso({ tipo: 'ok', texto: ok });
      onCambio();
    } catch (e) {
      setAviso({ tipo: 'error', texto: e.mensaje });
    } finally {
      setOcupado(false);
    }
  };

  const guardar = () =>
    accion(
      () =>
        corregirBorrador(borrador.id, {
          ...form,
          aptitudes: form.aptitudes
            .split(',')
            .map((a) => a.trim())
            .filter(Boolean),
        }),
      'Cambios guardados.',
    );

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <Tarjeta className="qo-profile" style={{ borderColor: '#4cd7f633' }}>
      <Titulo
        icono="edit_document"
        extra={
          <div className="qo-actions">
            <Chip tono={ESTADO_TONO[borrador.estado]}>{borrador.estado}</Chip>
            <button className="qo-close" onClick={() => setBorrador(null)} aria-label="Cerrar">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        }
      >
        {esBorrador ? 'Revisión humana del borrador' : 'Reto'}
      </Titulo>

      <div className="qo-grid dos" style={{ alignItems: 'start' }}>
        <div className="qo-fields">
          <label className="qo-field full">
            Título
            <input disabled={!esBorrador} value={form.titulo ?? ''} onChange={set('titulo')} />
          </label>
          <label className="qo-field full">
            Descripción pública
            <textarea disabled={!esBorrador} rows={7} value={form.descripcion_publica ?? ''} onChange={set('descripcion_publica')} />
          </label>
          <label className="qo-field full">
            Criterios de aceptación
            <textarea disabled={!esBorrador} rows={3} value={form.criterios_aceptacion ?? ''} onChange={set('criterios_aceptacion')} />
          </label>
          <label className="qo-field">
            Dificultad
            <select disabled={!esBorrador} value={form.dificultad ?? 'INTERMEDIO'} onChange={set('dificultad')}>
              <option>BASICO</option>
              <option>INTERMEDIO</option>
              <option>AVANZADO</option>
            </select>
          </label>
          <label className="qo-field">
            Aptitudes (separadas por coma)
            <input disabled={!esBorrador} value={form.aptitudes ?? ''} onChange={set('aptitudes')} />
          </label>
        </div>

        <div className="qo-list">
          <div className="qo-eyebrow">Pruebas propuestas ({borrador.pruebas.length})</div>
          {borrador.pruebas.map((p) => (
            <div key={p.id} className="qo-row" style={{ flexDirection: 'column', gap: 6 }}>
              <button
                type="button"
                onClick={() => setAbierta(abierta === p.id ? null : p.id)}
                style={{ display: 'flex', justifyContent: 'space-between', gap: 8, width: '100%', background: 'none', border: 0, color: 'inherit', textAlign: 'left', padding: 0 }}
              >
                <h3>{p.nombre}</h3>
                <span className="qo-tags" style={{ marginTop: 0, flexShrink: 0 }}>
                  <span className="qo-tag">{p.categoria}</span>
                  {p.obligatoria && <span className="qo-tag cyan">obligatoria</span>}
                  {p.contenido_ejecutable && <span className="qo-tag green">pytest</span>}
                </span>
              </button>
              <p>{p.condicion_aprobacion}</p>
              {abierta === p.id && p.contenido_ejecutable && (
                <pre className="qo-codigo">{p.contenido_ejecutable}</pre>
              )}
            </div>
          ))}
          {borrador.proyecto_base?.length > 0 && (
            <details className="qo-row" style={{ display: 'block' }}>
              <summary style={{ cursor: 'pointer' }}>Proyecto inicial ({borrador.proyecto_base.map((a) => a.ruta).join(', ')})</summary>
              {borrador.proyecto_base.map((a) => (
                <pre key={a.ruta} className="qo-codigo">{`# ${a.ruta}\n${a.contenido}`}</pre>
              ))}
            </details>
          )}
          <Aviso tipo="aviso">Las pruebas en código son una propuesta del modelo: validarlas contra una solución de referencia antes de publicar.</Aviso>
        </div>
      </div>

      <div className="qo-actions" style={{ marginTop: 22 }}>
        {esBorrador && (
          <>
            <Boton variante="secundario" icono="save" onClick={guardar} disabled={ocupado}>
              Guardar cambios
            </Boton>
            <Boton icono="publish" onClick={() => accion(() => publicarReto(borrador.id), 'Reto publicado en el catálogo.')} disabled={ocupado}>
              Publicar
            </Boton>
          </>
        )}
        {borrador.estado === 'PUBLICADO' && (
          <Boton variante="secundario" icono="lock" onClick={() => accion(() => cerrarReto(borrador.id), 'Reto cerrado.')} disabled={ocupado}>
            Cerrar reto
          </Boton>
        )}
      </div>
    </Tarjeta>
  );
}
