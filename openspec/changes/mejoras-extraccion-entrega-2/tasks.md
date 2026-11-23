# Tasks

## 1. Contrato v2 y contrato por versión

- [x] 1.1 En `entrega_2/clinica/contrato.py`: renombrar el contrato actual a `ExtraccionPacienteV1`, crear `ExtraccionPaciente` (v2: intenciones con `consulta_medica`, sin `es_consulta_medica`, validador de `otra` sola) y el registro `CONTRATOS` por versión; tests de v1 conservados y tests nuevos de v2 (`consulta_medica` válida, `es_consulta_medica` rechazada por campo extra, `["crear_turno", "otra"]` rechazada); verificar con `python -m pytest entrega_2`
- [x] 1.2 En `entrega_2/clinica/extractor.py`: `validar_respuesta(texto, version)` usa el contrato de la versión (`zeroshot` → V1, versión desconocida → el más nuevo) y `procesar_mensaje` le pasa la versión; tests de que `v1` sigue validando sus respuestas y `v2` las suyas; verificar con `pytest` y con `python entrega_2/app.py v1` en modo simulación

## 2. Set de evaluación (antes de cualquier corrida)

- [x] 2.1 Escribir `entrega_2/datos/set_evaluacion.json` con 50 mensajes etiquetados (formato de design D5; categorías simple, multi, ambiguo, medica, mixto, fuera_de_alcance, manipulacion; cada intención en ≥ 3 mensajes) y `entrega_2/tests/test_set_evaluacion.py` (50 mensajes, ids únicos, etiquetas válidas para el contrato v2, ≥ 3 por intención, ningún mensaje igual a un ejemplo de los prompts ni del lote); verificar con `pytest` y **con la revisión del usuario antes del commit**. Este commit tiene que quedar antes de la primera corrida de evaluación

## 3. Prompt v2

- [x] 3.1 Escribir `entrega_2/prompts/extraccion_v2.txt` (design D4: `consulta_medica`, sin flag, regla de `otra` sola, ejemplos de manipulación y de consulta médica, ejemplo mixto actualizado) y ajustar `test_prompt.py` para validar cada prompt contra el contrato de su versión; verificar con `pytest` (incluido que ningún ejemplo coincide con el lote ni con el set)
- [x] 3.2 Cambiar `PROMPT_VERSION` a `"v2"` en el extractor y actualizar `datos/lote_prueba.json` (simulaciones y textos de "qué observar" al contrato v2; el caso 4 espera `["consulta_medica"]`); verificar con `pytest` y `python entrega_2/app.py` en modo simulación

## 4. Matriz de la Entrega 1

- [x] 4.1 Actualizar `entrega_1/informe.md` (design D10): B.3 con 6 intenciones + `otra`, fila de consulta médica de B.4 con `consulta_medica`, nota de que se actualizó durante la Entrega 2; verificar con un test que las intenciones de la Matriz B.4 coinciden exactamente con el contrato v2

## 5. Evaluador

- [x] 5.1 Crear `entrega_2/evaluar.py` (design D6–D8: métricas, normalización de v1, comparación de entidades sin mayúsculas ni tildes, pausa configurable, guardado incremental en `evidencia/evaluacion_<version>.json`, reanudación, `--desde-cero`, tabla de fallos en Markdown) y `entrega_2/tests/test_evaluar.py` sin API (comparación de intenciones sin orden, entidades con `null` y con palabra clave, normalización de v1, mensaje con error cuenta como incorrecto, reanudación saltea ids ya evaluados); verificar con `pytest` y con `python entrega_2/evaluar.py v2` en modo simulación sobre 3 mensajes

## 6. Corridas reales con Groq

- [x] 6.1 Correr el lote de 4 con `v2`, guardar la salida en `entrega_2/evidencia/` y actualizar `entrega_2/resultados_lote.md` (tabla v2 como principal, la de v1 como antecedente); verificar que la tabla tiene las 4 filas de la corrida real con `prompt: v2`
- [x] 6.2 Correr `python entrega_2/evaluar.py v1` sobre los 50 mensajes y verificar que `evidencia/evaluacion_v1.json` tiene 50 resultados
- [x] 6.3 Correr `python entrega_2/evaluar.py v2` sobre los 50 mensajes y verificar que `evidencia/evaluacion_v2.json` tiene 50 resultados
- [x] 6.4 Escribir `entrega_2/evaluacion.md`: método (cómo se armó y etiquetó el set, criterios de los casos ambiguos, limitaciones), métricas de v1 y v2 lado a lado, veredicto sobre la hipótesis B.5 (≥ 90 %), análisis de los fallos por categoría; verificar que cada número coincide con los archivos de evidencia

## 7. Documentación y cierre

- [x] 7.1 Actualizar `entrega_2/informe.md`: A.1 (v1 contra v2 y zero-shot con los números de la evaluación), A.2 (prompt v2 completo y diferencias con v1), B.2 (contrato v2 y por qué `consulta_medica`), sección nueva de privacidad (design D9), resultados de la evaluación y C.2 actualizada; verificar contra la rúbrica que los 3 puntos (consulta médica, privacidad y evaluación) quedan cubiertos
- [x] 7.2 Actualizar `README.md` (comando de evaluación, `v2` por defecto, archivos nuevos en el árbol) y verificar que los comandos documentados corren tal cual desde la raíz
- [ ] 7.3 Verificación final: `pytest` en verde, intenciones idénticas en prompt v2, contrato v2 y Matriz B.4, ninguna key ni ID de organización en el historial (`git grep`), y `openspec validate --strict` del cambio

## Workflow follow-up

- Revisión del usuario y push.
- Archivar el cambio con `/opsx:archive` para actualizar las specs vigentes.
