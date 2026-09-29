# ADR-007 — Integracion de modelos de lenguaje con respaldo por reglas

- **Estado:** aceptada
- **Fecha:** 2026-09-28
- **Ambito:** backend, IA
- **Decide:** rol de Backend, Cloud DevOps & Database

## Contexto

La propuesta presenta cinco capacidades de IA: AI Pedagogical Scoper, Juez IA de arquitectura,
tutor, defensa tecnica y CV dinamico con grafo de aptitudes. Hasta esta decision el "Scoper" eran
cuatro expresiones regulares y las otras cuatro no existian. El criterio de *Ingenieria de
Software y Calidad Tecnica* nombra la integracion de IA de forma explicita.

Restricciones: presupuesto cero, capa gratuita con limites de frecuencia, material privado de las
organizaciones y la regla 17 del procedimiento (una solucion que incumple una prueba obligatoria
desaprueba, diga lo que diga cualquier otra senal).

## Decision

1. **Un solo cliente** (`app/servicios/llm.py`) sobre `/chat/completions` compatible con OpenAI.
   Proveedor por defecto: Groq (`llama-3.3-70b-versatile`), gratuito y sin tarjeta. Gemini,
   OpenRouter u OpenAI se usan cambiando `LLM_BASE_URL` y `LLM_MODEL`, sin tocar codigo.
2. **Salida JSON obligatoria y validada.** El modelo nunca decide la forma de los datos: puntajes
   se acotan a 0..100, categorias desconocidas se normalizan, rutas con `..` se descartan, el
   rendimiento nunca queda como prueba obligatoria.
3. **Saneamiento antes y despues de la llamada** en el Scoper: al proveedor solo llega texto con
   secretos, IPs internas, correos y cadenas de conexion reemplazados; la salida se vuelve a sanear.
4. **Lo medido separado de lo opinado.** El Juez IA guarda el analisis estatico (`ast`, sin
   ejecutar codigo del estudiante) aparte del juicio del modelo, y **no altera el dictamen**.
5. **Respaldo explicito, nunca silencioso.** Sin clave o con el proveedor caido: Scoper por reglas,
   Juez `SOLO_ESTATICA`, tutor solo con diagnosticos, defensa `SIN_CALIFICAR`, resumen de CV 503.
   Cada resultado guarda el `modelo` que lo produjo, igual que `version_evaluador` (ADR-002).
6. **Rango por XP ponderada**, no por conteo de PRs: dificultad del reto x calidad del Juez IA +
   defensa aprobada. Se deriva en cada consulta; revocar una credencial la retira en el acto.

## Alternativas descartadas

- **SDK de un proveedor concreto.** Acopla el codigo a una cuenta; `httpx` ya estaba instalado.
- **Defensa de opcion multiple con correccion simulada** (procedimiento V1). Con un modelo invocado
  de verdad se puede calificar la respuesta abierta; el informe declara que modelo califico.
- **Dejar que el Juez IA decida la aprobacion.** Contradice la regla 17 y haria el dictamen no
  reproducible.

## Consecuencias

- La suite (50 pruebas) nunca sale a la red: `conftest.py` vacia `LLM_API_KEY` y las pruebas de IA
  inyectan un doble con `llm.establecer_cliente`.
- Los limites de la capa gratuita (del orden de 30 peticiones por minuto) bastan para la demo; el
  tutor limita 6 consultas por minuto por usuario en memoria del proceso, valido para una instancia.
- El juez corre dentro del trabajo en segundo plano de la evaluacion: suma unos segundos antes de
  que la evaluacion aparezca FINALIZADA.
