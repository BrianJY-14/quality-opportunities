import { useEffect, useState } from 'react';

import { useAuthContext } from '../../context/AuthContext.jsx';

/** Formulario de ingreso con las clases de la tarjeta de la maqueta (scope .qo-login). */
export default function LoginForm({ onLogin, onCrearCuenta, Sim }) {
  const { login, status, error } = useAuthContext();
  const [tipo, setTipo] = useState('student');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [ver, setVer] = useState(false);

  useEffect(() => {
    if (status === 'success') onLogin?.();
  }, [status, onLogin]);

  // La misma cuenta puede ser estudiante y representante: el selector solo sugiere la cuenta demo.
  const elegir = (valor) => {
    setTipo(valor);
    setEmail(valor === 'student' ? 'carlos@uni.pe' : 'representante@ejemplo.pe');
  };

  const enviar = (e) => {
    e.preventDefault();
    login({ email, password });
  };

  return (
    <>
      <h1 id="login-title">ACCESO AL SISTEMA</h1>
      <p className="intro">Ingresa tus credenciales para continuar al entorno de aprendizaje técnico</p>
      <form onSubmit={enviar}>
        <fieldset className="account-types">
          <legend className="sr-only">Tipo de cuenta</legend>
          {[
            ['student', 'i-laptop', 'Estudiante', 'ACCESO INDIVIDUAL'],
            ['organization', 'i-building', 'Organización', 'PORTAL DE RETOS'],
          ].map(([valor, icono, nombre, detalle]) => (
            <label className="account-option" key={valor}>
              <input type="radio" name="account-type" value={valor} checked={tipo === valor} onChange={() => elegir(valor)} />
              <span className="option-content">
                <strong>
                  <Sim id={icono} /> {nombre}
                </strong>
                <small>{detalle}</small>
              </span>
            </label>
          ))}
        </fieldset>
        <div className="field">
          <div className="field-heading">
            <label htmlFor="email">
              <Sim id="i-mail" /> CORREO ELECTRÓNICO
            </label>
            <span className="field-hint">@uni.pe</span>
          </div>
          <input
            className="text-input"
            id="email"
            type="email"
            autoComplete="username"
            placeholder="carlos@uni.pe"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <div className="field-heading">
            <label htmlFor="password">
              <Sim id="i-key" /> CONTRASEÑA
            </label>
            <button className="text-button" type="button" onClick={() => setPassword('demo12345')}>
              Usar clave demo
            </button>
          </div>
          <div className="password-wrap">
            <input
              className="text-input"
              id="password"
              type={ver ? 'text' : 'password'}
              autoComplete="current-password"
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <button className="password-toggle" type="button" aria-label={ver ? 'Ocultar contraseña' : 'Mostrar contraseña'} aria-pressed={ver} onClick={() => setVer((v) => !v)}>
              <Sim id="i-eye" />
            </button>
          </div>
        </div>
        <div className="session-row">
          <label className="remember">
            <input type="checkbox" defaultChecked /> Mantener sesión activa
          </label>
          <span className="node-status">
            <span className="status-dot" />
            {status === 'loading' ? 'AUTENTICANDO' : 'NODE_READY'}
          </span>
        </div>
        <button className="primary-button" type="submit" disabled={status === 'loading'}>
          {status === 'loading' ? 'Autenticando…' : 'Ingresar'} <Sim id="i-arrow" />
        </button>
        <button className="secondary-button" type="button" onClick={onCrearCuenta}>
          <Sim id="i-user" /> Crear cuenta
        </button>
        <p className="demo-message" role="status" aria-live="polite" style={{ color: '#ffb4ab', textAlign: 'center', minHeight: 20, marginTop: 12 }}>
          {error}
        </p>
      </form>
    </>
  );
}
