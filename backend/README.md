# Backend

API del proyecto. Python 3.11 a 3.13 + FastAPI + SQLAlchemy 2.0 + PostgreSQL. Las funciones de IA
usan un LLM con API compatible con OpenAI (Groq por defecto) y funcionan en modo reglas sin clave.

## Ejecutar en local

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # Windows: copy .env.example .env
alembic upgrade head                                  # aplica el esquema
python seed.py                                        # datos de demostracion
uvicorn app.main:app --reload
```

Sin configurar nada corre sobre SQLite y con las funciones de IA en modo reglas. Para activar el
modelo basta poner `LLM_API_KEY` en `.env` (clave gratuita en <https://console.groq.com/keys>). Para Postgres basta cambiar `DATABASE_URL` por la
cadena del **Session pooler** de Supabase (host `aws-...pooler.supabase.com`, puerto 5432).
La conexion directa es IPv6 y no la alcanzan los PaaS gratuitos.

- API: <http://localhost:8000>
- Documentacion interactiva: <http://localhost:8000/docs>
- Estado del servicio: <http://localhost:8000/health>

Credenciales sembradas: `carlos@uni.pe` / `demo12345`.

## Calidad

Los cuatro comandos que corre CI en cada push a `main`:

```bash
ruff check .            # linter
ruff format --check .   # formato
alembic check           # las migraciones estan al dia con los modelos
pytest                  # 54 pruebas: flujo completo, errores, editor, evaluador, IA y robustez
```

Las pruebas aplican el esquema con Alembic, no con `create_all`: una migracion desincronizada
de los modelos hace fallar la suite en lugar de aparecer en el despliegue.

Tras editar un modelo, generar su migracion:

```bash
alembic revision --autogenerate -m "descripcion del cambio"
```

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `app/core/` | Configuracion, base de datos, seguridad, envoltura de errores |
| `app/dominio/` | Vocabularios del modelo (estados, categorias, funciones) |
| `app/models/` | Las 15 entidades del modelo de datos, agrupadas por modulo |
| `app/schemas/` | Contratos de entrada y salida (Pydantic) |
| `app/api/v1/` | Rutas, un archivo por modulo de dominio |
| `app/servicios/` | Los cuatro servicios y los dos puertos del diagrama de clases |
| `alembic/` | Migraciones versionadas del esquema |
| `tests/` | Camino feliz y casos de error criticos |

## Decisiones que conviene conocer antes de tocar el codigo

- **Monolito modular con puertos.** El scoper y el evaluador viven detras de interfaces
  (`app/servicios/puertos.py`) y se conmutan por variable de entorno. Ver `docs/adr/ADR-001`.
- **El motor de evaluacion se declara en el dato.** Cada ejecucion persiste y devuelve su motor.
  `simulado:v1` no ejecuta nada: deriva un resultado determinista de `sha256(commit + prueba)`.
  `e2b:v1` si ejecuta, en un sandbox aislado. Ver `docs/adr/ADR-002`.
- **Persistencia sincrona y evaluacion en segundo plano.** Endpoints con `def`, sesion por
  peticion, y la evaluacion en `BackgroundTasks` con su propia sesion. El envio responde `202`
  y el frontend consulta el estado. Ver `docs/adr/ADR-003`.
- **CORS por lista blanca y autenticacion Bearer.** El frontend es estatico y vive en otro
  origen. Ver `docs/adr/ADR-004`.
- **Esquema versionado con Alembic, verificado en CI.** La aplicacion no crea tablas al arrancar.
  Ver `docs/adr/ADR-005`.

## Logs

Salida JSON por linea (`LOG_JSON=true`), con `request_id` en cada peticion — devuelto tambien en
la cabecera `X-Request-ID` — y `submission_id` en todo lo que emite la evaluacion en segundo
plano. Una entrega concreta se rastrea asi:

```bash
grep '"submission_id": "<uuid>"' logs.txt
```

En local, `LOG_JSON=false` deja la salida en texto legible.

El contrato completo de la API esta en [`docs/api.md`](../docs/api.md).

## Correspondencia con el modelo de datos

Las 14 entidades del E-R son 14 de las 15 tablas del esquema, con el mismo nombre. La quinceava,
`espacio_trabajo`, es el borrador del editor web y no pertenece al E-R conceptual. Los cuatro servicios
y los dos puertos del diagrama de clases son los seis modulos de `app/servicios/`:

| Clasificador UML | Modulo |
| --- | --- |
| `ServicioSeguridad` | `servicios/seguridad.py` |
| `ServicioRetos` | `servicios/retos.py` |
| `ServicioEvaluacion` | `servicios/evaluacion.py` |
| `ServicioCertificacion` | `servicios/certificacion.py` |
| `PreparadorIA` | `servicios/puertos.py` → `preparador_reglas.py` |
| `EvaluadorAislado` | `servicios/puertos.py` → `evaluador_simulado.py` y `evaluador_e2b.py` |

`app/servicios/auditoria.py` implementa RN-AUD-01, que el UML no dibuja como servicio.

## Estado de los modulos

Todo el flujo del diseno esta implementado y probado: solicitud, preparacion con revision humana,
publicacion, participacion, borrador en el editor web, entrega, evaluacion, reevaluacion, emision,
revocacion, recertificacion, perfil publico y bitacora.
