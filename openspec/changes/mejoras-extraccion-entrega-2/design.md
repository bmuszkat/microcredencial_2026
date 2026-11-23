# Design

## Context

- El componente de la Entrega 2 está en `entrega_2/clinica/` y tiene un solo contrato (`ExtraccionPaciente`, con `es_consulta_medica`) y dos prompts (`v1` few-shot y `zeroshot`, que es el `v1` sin ejemplos). `extractor.procesar_mensaje()` valida toda respuesta contra ese único contrato.
- Las corridas de `v1` están documentadas en `resultados_lote.md` y en `entrega_2/evidencia/`. Tienen que seguir siendo reproducibles.
- El límite gratuito de Groq es de 8.000 tokens por minuto y cada llamada usa ≈ 2.500 tokens (≈ 3 llamadas por minuto). Los reintentos ya respetan `Retry-After` (implementado antes de este cambio; acá solo se actualiza la spec).
- Motivación: ver proposal.md.

## Goals / Non-Goals

**Goals:**
- Que `v1` y `v2` convivan: cada versión de prompt valida contra su propio contrato.
- Que la evaluación sea honesta: las respuestas esperadas se escriben y se commitean **antes** de la primera corrida.
- Que una corrida de evaluación sobreviva a los límites de Groq sin intervención.

**Non-Goals:**
- No se implementa la anonimización (queda documentada para la Entrega 3).
- No se busca un puntaje alto ajustando el prompt contra el set: el set mide, no entrena. Si `v2` no llega al 90 %, se documenta.
- No se automatiza la evaluación en CI.

## Decisions

### D1. `consulta_medica` reemplaza al flag `es_consulta_medica`
Con una intención propia, el backend enruta la consulta médica a una persona (Matriz B.4, riesgo ALTO) sin mirar un segundo campo, y `otra` queda para lo que se repregunta o se descarta. Mantener también el flag dejaría dos formas de decir lo mismo y la posibilidad de contradicción (`["crear_turno"]` con flag `true` contra `["crear_turno", "consulta_medica"]`).
*Alternativa descartada:* agregar la intención y conservar el flag. Es redundante.

### D2. `otra` no se combina (validador del contrato)
Sale de la evaluación de la Entrega 2: en el caso del síntoma con turno, zero-shot devolvía `["crear_turno", "otra"]` en 3 de 3 corridas. Con `consulta_medica` ya no hay motivo legítimo para combinar `otra`, así que el contrato lo rechaza (CONTRATO) y el prompt lo prohíbe (regla nueva).

### D3. Contrato por versión de prompt
`contrato.py` define `ExtraccionPacienteV1` (el actual: `es_consulta_medica`, 6 intenciones) y `ExtraccionPaciente` (v2: `consulta_medica`, sin flag, `otra` sola), y un registro `CONTRATOS = {"v1": V1, "zeroshot": V1, "v2": V2}`. `extractor.validar_respuesta(texto, version)` elige el contrato con ese registro; una versión que no esté en el registro usa el contrato más nuevo.
*Por qué:* sin esto, `python entrega_2/app.py v1` fallaría en CONTRATO en todos los casos (el v1 devuelve `es_consulta_medica`, que el contrato v2 rechaza por `extra="forbid"`), y la comparación v1 contra v2 que pide la consigna sería imposible.
*Alternativa descartada:* dejar el `v1` sin poder ejecutarse "como registro". Rompe la reproducibilidad de lo ya documentado.

### D4. Prompt v2 = v1 + tres cambios
1. `consulta_medica` en la lista de intenciones (y fuera el flag del schema).
2. Regla: `otra` solo cuando no hay ningún otro pedido; no se combina.
3. Dos ejemplos few-shot nuevos: uno de **manipulación** (extrae el pedido real ignorando la "autoridad"), que era el caso menos estable, y el de **consulta médica pura**. El ejemplo del síntoma con turno se actualiza a `["crear_turno", "consulta_medica"]`.
Ningún ejemplo coincide con los mensajes del lote ni del set de evaluación (lo verifica un test).

### D5. Formato del set de evaluación
`entrega_2/datos/set_evaluacion.json`: lista de 50 objetos `{"id", "categoria", "mensaje", "esperado": {"intenciones": [...], "dni", "profesional", "fecha_turno_actual", "fecha_deseada", "estudio"}}`.
- `dni`: dígitos exactos o `null`.
- Las demás entidades: una **palabra clave** que el valor del modelo tiene que contener (por ejemplo `"López"` o `"viernes"`), o `null`. Exigir el texto literal sería injusto: "jueves 15 hs" y "jueves a las 15" son igual de correctos.
- Categorías: simple, multi, ambiguo, medica, mixto, fuera_de_alcance, manipulacion.
- Las etiquetas se commitean en una tarea **anterior** a la primera corrida (queda en el historial de git que no se ajustaron después).

### D6. Métricas y comparación de entidades
`evaluar.py` reutiliza `extractor.procesar_mensaje()` (el mismo camino que `app.py`) y calcula, sobre los 50:
- **JSON válido**: no terminó en COMUNICACION ni FORMATO.
- **Cumple el contrato**: además, no terminó en CONTRATO.
- **Intenciones exactas**: el conjunto de intenciones coincide (el orden no importa).
- **Entidades correctas**: proporción de las 250 entidades (50 × 5) correctas, comparando sin mayúsculas ni tildes.
- **Mensajes completamente correctos**: intenciones y las 5 entidades. Esta es la métrica de la hipótesis B.5 (intención + DNI, profesional y fecha).
La regla de DNI (REGLA) no se descuenta del contrato: un DNI inválido que el modelo copió fielmente es un acierto de extracción.

### D7. Normalización de v1
Para comparar `v1` con las etiquetas vigentes, `evaluar.py` lee la respuesta cruda de `v1` y traduce: si `es_consulta_medica` es `true`, `otra` pasa a `consulta_medica` (y si no había `otra`, se agrega `consulta_medica`). Es la equivalencia exacta entre los dos contratos (spec `evaluacion-extraccion`).

### D8. Corridas largas y retomables
- Una pausa configurable entre llamadas (`--pausa`, por defecto 20 s) para quedar por debajo de 3 llamadas por minuto; sumada a los reintentos con `Retry-After`, evita la mayoría de los 429.
- Cada resultado se guarda apenas llega en `entrega_2/evidencia/evaluacion_<version>.json`; al relanzar, los `id` ya evaluados se saltean. `--desde-cero` borra y empieza de nuevo.
- Al terminar imprime las métricas y la tabla de fallos en Markdown, lista para `evaluacion.md`.
- Duración esperada: 50 × ~20 s ≈ 17 minutos por versión.

### D9. Privacidad: documentar, no implementar
Sección nueva en el informe de la Entrega 2 con: qué datos salen hacia la API (DNI, nombre, profesional, estudios y síntomas), por qué importa (datos de salud, Ley 25.326, proveedor fuera del país), y opciones ordenadas por esfuerzo: (a) acuerdo de tratamiento con el proveedor o modelo alojado localmente; (b) **extraer el DNI con una regex en código y enviar `[DNI]` al LLM**, que encaja con "la IA interpreta, el código es la autoridad"; (c) seudonimizar nombres. La opción (b) queda propuesta para la Entrega 3.

### D10. Matriz de la Entrega 1
En `entrega_1/informe.md`: B.3 pasa a "6 intenciones + `otra`", la fila de consulta médica de B.4 cambia `otra` por `consulta_medica`, y se agrega una nota visible de que la Matriz se actualizó durante la Entrega 2, para que el cambio sea trazable.

## Risks / Trade-offs

- [El set lo escribe el mismo equipo que escribe el prompt: puede quedar sesgado a favor] → Etiquetas commiteadas antes de correr, categorías difíciles incluidas a propósito (ambiguos, mixtos, manipulación) y ningún mensaje copiado de los ejemplos. Se reconoce la limitación en `evaluacion.md`.
- [Etiquetas discutibles en casos ambiguos] → En los ambiguos se etiqueta lo que pediría la Matriz (por ejemplo, las dos intenciones si el paciente duda) y se explica el criterio en `evaluacion.md`.
- [Variabilidad a temperatura 0] → Se reporta una corrida por versión y se aclara que puede variar unos puntos; no se elige "la mejor de varias".
- [Tiempo y límite de Groq] → Pausa entre llamadas, reanudación y reintentos con `Retry-After`.
- [Cambio de contrato rompe tests existentes] → Los tests del contrato se duplican por versión; los de `v1` se conservan.

## Migration Plan

1. El contrato v2 y el registro por versión se agregan sin tocar el comportamiento de `v1`.
2. `PROMPT_VERSION` pasa a `"v2"`: `app.py` sin argumento usa `v2`; `app.py v1` sigue funcionando igual que antes.
3. Rollback: volver `PROMPT_VERSION` a `"v1"`.
