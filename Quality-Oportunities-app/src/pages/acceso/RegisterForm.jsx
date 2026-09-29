import { useEffect, useState } from 'react';

import { useAuthContext } from '../../context/AuthContext.jsx';

/** Registro con perfil de estudiante. Al crear la cuenta inicia sesion directamente. */
export default function RegisterForm({ onLogin, onVolver, Sim }) {
  const { registro, status, error } = useAuthContext();
  const [f, setF] = useState({ nombre: '', email: '', password: '', nombre_publico: '', universidad: 'UNI', carrera: '', ciclo: '' });

  useEffect(() => {
    if (status === 'success') onLogin?.();
  }, [status, onLogin]);

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const enviar = (e) => {
    e.preventDefault();
    registro({
      email: f.email,
      password: f.password,
      nombre: f.nombre,
      perfil: {
        nombre_publico: f.nombre_publico || f.nombre.toLowerCase().trim().replace(/\s+/g, '-'),
        universidad: f.universidad || null,
        carrera: f.carrera || null,
        ciclo: f.ciclo ? Number(f.ciclo) : null,
      },
    });
  };

  const campo = (id, etiqueta, icono, props = {}) => (
    <div className="field">
      <div className="field-heading">
        <label htmlFor={id}>
          <Sim id={icono} /> {etiqueta}
        </label>
      </div>
      <input className="text-input" id={id} value={f[id]} onChange={set(id)} {...props} />
    </div>
  );

  return (
    <>
      <h1 id="login-title">CREAR CUENTA</h1>
      <p className="intro">El nombre público es la dirección del CV dinámico verificable.</p>
      <form onSubmit={enviar}>
        {campo('nombre', 'NOMBRE COMPLETO', 'i-user', { required: true, minLength: 2 })}
        {campo('email', 'CORREO ELECTRÓNICO', 'i-mail', { type: 'email', required: true, autoComplete: 'username' })}
        {campo('password', 'CONTRASEÑA (MÍN. 8)', 'i-key', { type: 'password', required: true, minLength: 8, autoComplete: 'new-password' })}
        {campo('nombre_publico', 'NOMBRE PÚBLICO', 'i-network', { placeholder: 'brian-jara' })}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 76px', gap: 8 }}>
          {campo('universidad', 'UNIVERSIDAD', 'i-building')}
          {campo('carrera', 'CARRERA', 'i-laptop')}
          {campo('ciclo', 'CICLO', 'i-gauge', { type: 'number', min: 1, max: 12 })}
        </div>
        <button className="primary-button" type="submit" disabled={status === 'loading'}>
          {status === 'loading' ? 'Creando…' : 'Crear cuenta y entrar'} <Sim id="i-arrow" />
        </button>
        <button className="secondary-button" type="button" onClick={onVolver}>
          <Sim id="i-user" /> Ya tengo cuenta
        </button>
        <p role="status" style={{ color: '#ffb4ab', textAlign: 'center', minHeight: 20, marginTop: 12 }}>
          {error}
        </p>
      </form>
    </>
  );
}
