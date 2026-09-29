import { useCallback, useEffect, useState } from 'react';

import {
  abrirEspacio,
  enviarEntrega,
  guardarEspacio,
  misParticipaciones,
  participar,
  verReto,
} from '../../service/api.js';
import TutorPanel from '../../components/TutorPanel.jsx';
import { Aviso, Boton, Chip, Icono, Pagina, Tarjeta, Titulo } from '../../components/ui.jsx';

const PLANTILLA = `# Escribe aqui tu solucion.
# El archivo principal del proyecto es main.py.

def procesar(entrada):
    return entrada
`;

/**
 * Editor conectado al backend.
 *
 * Al montar crea la participacion (o recupera la que ya existia) y abre el espacio de trabajo.
 * Guardar NO crea una entrega ni incrementa el numero de intento: eso solo ocurre al enviar.
 *
 * `revision` es control de concurrencia optimista: se envia la revision sobre la que se edito y
 * el servidor rechaza con 409 si otra pestana guardo antes, en vez de pisar el trabajo ajeno.
 */
export default function EspacioTrabajoPage({ retoId, onEnviar, onVolver }) {
  const [reto, setReto] = useState(null);
  const [participacionId, setParticipacionId] = useState(null);
  const [espacio, setEspacio] = useState(null);
  const [archivos, setArchivos] = useState([]);
  const [activo, setActivo] = useState(0);
  const [sucio, setSucio] = useState(false);
  const [aviso, setAviso] = useState(null); // { tipo: 'ok'|'error', texto }
  const [ocupado, setOcupado] = useState(false);
  const [cargando, setCargando] = useState(true);

  // --- arranque: participacion + espacio + detalle del reto ------------------
  useEffect(() => {
    if (!retoId) return undefined;
    let vigente = true;

    (async () => {
      try {
        const detalle = await verReto(retoId);
        if (vigente) setReto(detalle);

        let participacion;
        try {
          participacion = await participar(retoId);
        } catch (e) {
          // Ya participaba: se recupera la existente en vez de fallar.
          if (e.codigo !== 'PARTICIPACION_YA_EXISTE') throw e;
          const mias = await misParticipaciones();
          participacion = mias.find((p) => p.reto_id === retoId);
        }
        if (!vigente || !participacion) return;
        setParticipacionId(participacion.id);

        const w = await abrirEspacio(participacion.id);
        if (!vigente) return;
        setEspacio(w);
        const iniciales =
          w.archivos.length > 0
            ? w.archivos.map(({ ruta, contenido }) => ({ ruta, contenido }))
            : [{ ruta: 'main.py', contenido: PLANTILLA }];
        setArchivos(iniciales);
        // El proyecto base puede traer README.md; se abre primero el archivo de entrada.
        setActivo(Math.max(0, iniciales.findIndex((a) => a.ruta === 'main.py')));
      } catch (e) {
        if (vigente) setAviso({ tipo: 'error', texto: e.mensaje ?? 'No se pudo abrir el espacio.' });
      } finally {
        if (vigente) setCargando(false);
      }
    })();

    return () => {
      vigente = false;
    };
  }, [retoId]);

  // --- guardar ---------------------------------------------------------------
  const guardar = useCallback(async () => {
    if (!participacionId || !espacio || ocupado) return;
    setOcupado(true);
    setAviso(null);
    try {
      const actualizado = await guardarEspacio(participacionId, espacio.revision, archivos);
      setEspacio(actualizado);
      setSucio(false);
      setAviso({ tipo: 'ok', texto: `Guardado. Revisión ${actualizado.revision}.` });
    } catch (e) {
      setAviso({
        tipo: 'error',
        texto:
          e.codigo === 'BORRADOR_DESACTUALIZADO'
            ? 'Otra pestaña guardó antes. Recarga para no perder su trabajo.'
            : (e.mensaje ?? 'No se pudo guardar.'),
      });
    } finally {
      setOcupado(false);
    }
  }, [participacionId, espacio, archivos, ocupado]);

  // --- enviar ----------------------------------------------------------------
  const enviar = useCallback(async () => {
    if (!participacionId || ocupado) return;
    setOcupado(true);
    setAviso(null);
    try {
      if (sucio) await guardar();
      // Identificador del intento. Con el evaluador simulado determina el resultado; con el de
      // sandbox lo que se ejecuta es el contenido del espacio de trabajo.
      const commit = Math.random().toString(16).slice(2, 14);
      const aceptada = await enviarEntrega(participacionId, {
        repositorio: reto?.repositorio_base ?? 'https://github.com/demo/reto',
        commit,
      });
      onEnviar?.(aceptada.evaluacion_id, reto?.titulo);
    } catch (e) {
      setAviso({ tipo: 'error', texto: e.mensaje ?? 'No se pudo enviar.' });
    } finally {
      setOcupado(false);
    }
  }, [participacionId, ocupado, sucio, guardar, reto, onEnviar]);

  // Ctrl+S guarda, como en cualquier editor.
  useEffect(() => {
    const alPulsar = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        guardar();
      }
    };
    window.addEventListener('keydown', alPulsar);
    return () => window.removeEventListener('keydown', alPulsar);
  }, [guardar]);

  const cambiarContenido = (valor) => {
    setArchivos((previos) => previos.map((a, i) => (i === activo ? { ...a, contenido: valor } : a)));
    setSucio(true);
  };

  const nuevoArchivo = () => {
    const ruta = window.prompt('Nombre del archivo (.py .txt .md .json .csv .toml)');
    if (!ruta) return;
    setArchivos((previos) => [...previos, { ruta, contenido: '' }]);
    setActivo(archivos.length);
    setSucio(true);
  };

  if (!retoId) {
    return (
      <Pagina>
        <Aviso>Selecciona un reto del catálogo.</Aviso>
      </Pagina>
    );
  }

  const bloqueado = espacio && !espacio.puede_enviar;
  const bytes = new Blob([archivos.map((a) => a.contenido).join('')]).size;

  return (
    <Pagina>
      <div className="qo-toolbar-sticky">
        <div className="qo-actions">
          <Boton variante="fantasma" icono="arrow_back" onClick={onVolver}>
            Detalle
          </Boton>
          <span className="qo-meta">
            {reto?.titulo ?? 'Cargando…'}
            {espacio && ` · revisión ${espacio.revision}`}
            {sucio && <span style={{ color: 'var(--qo-yellow)' }}> · sin guardar</span>}
          </span>
        </div>
        <div className="qo-actions">
          <Boton variante="secundario" icono="save" onClick={guardar} disabled={ocupado || !espacio}>
            Guardar
          </Boton>
          <Boton icono="rocket_launch" onClick={enviar} disabled={ocupado || !espacio || bloqueado} title={bloqueado ? espacio.motivo_bloqueo : undefined}>
            Enviar solución
          </Boton>
        </div>
      </div>

      {aviso && (
        <div style={{ marginBottom: 16 }}>
          <Aviso tipo={aviso.tipo === 'ok' ? 'ok' : 'error'}>{aviso.texto}</Aviso>
        </div>
      )}
      {bloqueado && (
        <div style={{ marginBottom: 16 }}>
          <Aviso tipo="aviso">{espacio.motivo_bloqueo}</Aviso>
        </div>
      )}

      <div className="qo-two">
        <div className="qo-editor">
          <div className="qo-editor-tabs" role="tablist">
            {archivos.map((a, i) => (
              <button key={a.ruta} role="tab" aria-selected={i === activo} onClick={() => setActivo(i)}>
                <Icono nombre={a.ruta.endsWith('.py') ? 'code' : 'description'} style={{ fontSize: 16 }} />
                {a.ruta}
              </button>
            ))}
            <button onClick={nuevoArchivo} title="Añadir archivo" aria-label="Añadir archivo">
              <Icono nombre="add" style={{ fontSize: 16 }} />
            </button>
          </div>
          <textarea
            value={archivos[activo]?.contenido ?? ''}
            onChange={(e) => cambiarContenido(e.target.value)}
            spellCheck={false}
            disabled={cargando}
            placeholder={cargando ? 'Abriendo el espacio de trabajo…' : ''}
            aria-label="Editor de código"
            onKeyDown={(e) => {
              if (e.key === 'Tab') {
                e.preventDefault();
                const t = e.target;
                const { selectionStart: a, selectionEnd: b } = t;
                cambiarContenido(`${t.value.slice(0, a)}    ${t.value.slice(b)}`);
                requestAnimationFrame(() => t.setSelectionRange(a + 4, a + 4));
              }
            }}
          />
          <div className="qo-editor-foot">
            <span>{archivos.length} archivo(s) · máximo 20 · Python · UTF-8</span>
            <span>{bytes} bytes · máximo 1 MiB · Ctrl+S guarda</span>
          </div>
        </div>

        <div className="qo-stack">
          <TutorPanel
            participacionId={participacionId}
            sucio={sucio}
            guardarAntes={guardar}
            onIrALinea={(ruta) => {
              const i = archivos.findIndex((a) => a.ruta === ruta);
              if (i >= 0) setActivo(i);
            }}
          />
          <Tarjeta>
            <Titulo icono="task_alt" extra={reto && <Chip tono="primario">{reto.pruebas_obligatorias} obligatorias</Chip>}>
              Pruebas del reto
            </Titulo>
            <div className="qo-list">
              {(reto?.pruebas ?? []).map((p) => (
                <div key={p.id} className="qo-row" style={{ justifyContent: 'flex-start' }}>
                  <Icono nombre={p.obligatoria ? 'check_circle' : 'radio_button_unchecked'} style={{ color: p.obligatoria ? 'var(--qo-cyan)' : '#7f8f94', fontSize: 20 }} />
                  <div>
                    <h3>{p.nombre}</h3>
                    <p className="qo-meta">{p.condicion_aprobacion}</p>
                  </div>
                </div>
              ))}
            </div>
          </Tarjeta>
          <Aviso>Guardar conserva el borrador. Enviar crea un intento oficial, congela el proyecto y lanza la evaluación.</Aviso>
        </div>
      </div>
    </Pagina>
  );
}
