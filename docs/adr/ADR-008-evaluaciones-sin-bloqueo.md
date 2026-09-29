# ADR-008 — Ninguna evaluacion puede quedar en EN_EJECUCION

- **Estado:** aceptada
- **Fecha:** 2026-09-28
- **Ambito:** backend, evaluacion
- **Decide:** rol de Backend, Cloud DevOps & Database

## Contexto

En la demostracion del hackaton, al pulsar «Enviar solucion» algunas evaluaciones quedaron en
`EN_EJECUCION` sin resultados y el frontend consulto su estado sin fin. Se mitigo en Supabase con
un trigger (`trg_evaluacion_diferida`) que simulaba la evaluacion con `pg_sleep`.

Las capturas de excepciones de `_procesar` ya existian. Quedaban tres huecos que ningun
`try/except` cubre:

1. **Una llamada que no termina.** `Sandbox.create` de E2B solo recibia `timeout` (vida del
   sandbox), no `request_timeout`: si la creacion se quedaba esperando la imagen, el hilo se
   bloqueaba sin lanzar nada.
2. **Un proceso que muere.** `BackgroundTasks` vive en memoria. Render reinicia o duerme el plan
   gratuito, y el trabajo a medias desaparece sin que nadie cierre la fila.
3. **Excepciones fuera del bloque del evaluador** (persistir resultados, dictaminar, emitir).

## Decision

- `request_timeout=45` en la creacion del sandbox.
- El evaluador corre en un hilo con techo `LIMITE_EVALUACION_S` (240 s). Vencido, `FalloEvaluador`
  y la evaluacion cierra en `ERROR_TECNICO` sin dictamen (RN-EVAL-03), no en un estado `FALLIDA`
  nuevo: el estado ya existia y el frontend ya lo muestra como fallo del entorno, no del alumno.
- `procesar` tiene una red final que cierra en `ERROR_TECNICO` cualquier excepcion restante.
- `cerrar_colgadas` cierra las evaluaciones en curso mas alla del limite. Se ejecuta al arrancar el
  servicio (con margen cero: el proceso anterior ya no existe) y al consultar una evaluacion.
- El frontend consulta con espera creciente, deja de hacerlo a los 6 minutos y ofrece
  «Reevaluar la misma entrega» ante un `ERROR_TECNICO`.
- La lectura de credenciales tolera `criterios_aceptacion` como lista y claves ausentes, porque la
  correccion manual en Supabase dejo filas con esa forma.

## Consecuencias

- **Antes de desplegar** hay que retirar el trigger de Supabase; si no, finaliza la evaluacion al
  insertarla y el evaluador real (y el Juez IA) nunca corren:

  ```sql
  DROP TRIGGER IF EXISTS trg_evaluacion_diferida ON public.evaluacion;
  DROP FUNCTION IF EXISTS public.trg_evaluar_con_espera_simulada();
  ```

- Sigue sin haber una cola durable (procedimiento, seccion 7): una evaluacion interrumpida no se
  reanuda, se cierra y se reevalua. Para varias instancias habria que mover el trabajo a una cola.
- Pruebas de regresion en `backend/tests/test_robustez.py`.
