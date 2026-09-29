# Decisiones de arquitectura (ADR)

Registro de decisiones tomadas durante la jornada, con sus alternativas descartadas y sus
consecuencias. Cada una responde a una restriccion real: tiempo, plataforma de despliegue o
criterio de evaluacion.

| ADR | Decision |
| --- | --- |
| [ADR-001](ADR-001-monolito-modular.md) | Monolito modular con puertos en lugar de servicios separados |
| [ADR-002](ADR-002-evaluador-conmutable.md) | Evaluador y preparador tras puertos, con la implementacion declarada en el dato |
| [ADR-003](ADR-003-sincronia-y-trabajos-en-segundo-plano.md) | Acceso sincrono a base de datos y evaluacion en segundo plano |
| [ADR-004](ADR-004-frontend-estatico-y-autenticacion.md) | Frontend estatico en GitHub Pages, CORS por lista blanca y autenticacion Bearer |
| [ADR-005](ADR-005-esquema-versionado-y-verificacion-en-ci.md) | Esquema versionado con Alembic y verificacion automatica en CI |
| [ADR-006](ADR-006-permisos-por-representacion.md) | Permisos derivados de la representacion, no de un rol global |
| [ADR-007](ADR-007-integracion-de-ia.md) | Modelos de lenguaje tras un cliente comun, salida validada y respaldo por reglas |
| [ADR-008](ADR-008-evaluaciones-sin-bloqueo.md) | Ninguna evaluacion queda en EN_EJECUCION: limite, red final y cierre de huerfanas |
