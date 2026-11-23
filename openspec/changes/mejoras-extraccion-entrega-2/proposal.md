# Proposal

## Why

Al revisar la Entrega 2 encontramos tres puntos para mejorar: (1) la consulta médica cae en `otra`, que mezcla "no entendí el mensaje" con "esto no lo puedo responder", y el backend tiene que tratarlas distinto; (2) en un caso real estaríamos enviando DNI y estudios de pacientes a una API externa y ese riesgo no está analizado; (3) la hipótesis más riesgosa de la Entrega 1 (B.5: el modelo extrae bien ≥ 90 % de los mensajes) se puede medir de verdad con el set de 50 mensajes prometido en B.3, y hasta ahora solo corrimos 4. Además, durante las pruebas corregimos en código dos comportamientos que la spec vigente no refleja (reintentos que respetan `Retry-After` y el 400 `json_validate_failed` como FORMATO).

## What Changes

- **BREAKING (contrato):** nueva intención `consulta_medica`; se elimina el campo `es_consulta_medica`. `otra` queda solo para lo que está fuera de alcance o no se entiende y no se combina con otras intenciones. *(Punto 1)*
- **Matriz de la Entrega 1 actualizada** (B.3 y B.4 de `entrega_1/informe.md`) con `consulta_medica`, para que las intenciones del prompt sigan coincidiendo exactamente con la Matriz (consigna E2, criterio 1). *(Punto 1)*
- **Prompt `v2`** (el `v1` se conserva como registro): suma `consulta_medica`, un ejemplo few-shot de manipulación y la regla de que `otra` no se combina, que son las mejoras propuestas en la reflexión C.2. El sistema pasa a usar `v2` por defecto. *(Punto 1, consigna E2 "comparar v1 vs v2")*
- **Contrato por versión de prompt:** cada versión valida contra su propio contrato, para que las corridas de `v1` sigan siendo reproducibles. *(Consigna E2, prompt versionado)*
- **Lote de 4 actualizado y corrido con `v2`.** *(Consigna E2, C.1)*
- **Riesgo de privacidad documentado y analizado** en el informe de la Entrega 2: qué datos personales salen hacia la API, por qué importa (Ley 25.326), opciones de mitigación y si conviene anonimizar antes de llamar al LLM. *(Punto 2)*
- **Evaluación sobre 50 mensajes etiquetados:** set de evaluación con la respuesta esperada de cada mensaje, escrito antes de correr, y un script que mide % de JSON válido, % de intenciones exactas, % de entidades correctas y % de mensajes completamente correctos. Se corre con `v1` y con `v2` y se documenta el resultado frente al 90 % de la hipótesis B.5. *(Punto 3, Entrega 1 B.3 y B.5)*
- **Specs al día con el código:** los reintentos esperan lo que pide la API y el rechazo de JSON del proveedor es FORMATO.

Los tres puntos se resuelven en este cambio, dentro de la Entrega 2.

### Fuera de alcance

- La **implementación** de la anonimización (por ejemplo, extraer el DNI con código y enviar `[DNI]` al LLM). El análisis sí está en este cambio; construirla queda como opción para cuando el componente se integre al workflow (Entrega 3).
- Convertir fechas relativas, agenda, herramientas, identidad contra el padrón y respuesta al paciente → **Entrega 3** (sin cambios respecto de la propuesta anterior).
- Ampliar el set de evaluación más allá de 50 mensajes o automatizarlo en CI → **Entrega 4** (matriz de pruebas).

## Capabilities

### New Capabilities

- `evaluacion-extraccion`: medir la calidad de la extracción contra un set de mensajes etiquetados, por versión de prompt, con métricas comparables entre versiones.

### Modified Capabilities

- `extraccion-mensajes`: el schema pierde `es_consulta_medica`, las intenciones suman `consulta_medica` y `otra` cambia de significado; el contrato depende de la versión de prompt; el rechazo de JSON del proveedor es FORMATO.
- `proveedor-llm`: los reintentos ante 429/503 respetan el tiempo de espera que indica la API.

## Impact

- **Código:** `entrega_2/clinica/contrato.py` (contrato v2 y registro por versión), `extractor.py` (elige el contrato según la versión y usa `v2` por defecto), `entrega_2/app.py` (sin cambios de interfaz), nuevo `entrega_2/evaluar.py`.
- **Datos y prompts:** nuevo `prompts/extraccion_v2.txt`, `datos/lote_prueba.json` actualizado, nuevo `datos/set_evaluacion.json`.
- **Documentación:** `entrega_1/informe.md` (Matriz B.3 y B.4), `entrega_2/informe.md`, `entrega_2/resultados_lote.md`, nuevo `entrega_2/evaluacion.md`, `README.md`.
- **Costo de API:** cada corrida de evaluación son 50 llamadas; con el límite gratuito de Groq (≈ 3 llamadas por minuto con este prompt) tarda unos 15 a 20 minutos.
