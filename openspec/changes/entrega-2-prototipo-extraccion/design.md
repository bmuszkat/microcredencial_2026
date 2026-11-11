# Design

## Context

- El repo tiene `entrega_1/` (informe + `main.py`, la práctica de la Clase 1 con un prompt ingenuo) y un `.env` en la raíz con `GROQ_API_KEY`. No hay código reutilizable para esta entrega más allá de la idea de multi-proveedor.
- La cátedra publicó un ejemplo de referencia para Ortelana (paquete `ortelana/` con `config`, `contrato`, `llm`, `reglas`, `extractor`; prompt versionado; lote en JSON; tests sin API). Se toma como guía de estructura, adaptado al caso de la clínica.
- Restricciones de la consigna: el entregable vive en `entrega_2/`, el script se llama `app.py`, el docente lo tiene que poder correr con una key propia y ninguna key puede entrar al repo (ver proposal.md).

## Goals / Non-Goals

**Goals:**
- Que el componente se pueda correr con un solo comando desde la raíz del repo, con o sin key.
- Que cambiar de proveedor, de modelo o de versión de prompt no requiera tocar código.
- Que cada etapa de validación sea una función pura testeable sin API.

**Non-Goals:**
- No se usan SDKs de proveedores (ni `groq`, ni `openai`, ni `anthropic`): todas las llamadas son HTTP directo.
- No se persiste nada: el componente procesa mensajes y devuelve resultados en memoria.
- No se optimiza costo ni latencia más allá de temperatura 0 y un timeout.

## Decisions

### D1. `intenciones` es una lista, no una intención única
La plantilla de la consigna y el ejemplo de la cátedra usan `"intencion": "X"`. Elegimos `"intenciones": [...]` porque la Entrega 1 se comprometió a soportar varios pedidos por mensaje: el paso 2 del journey (B.2) detecta `modificar_turno` + `consultar_resultado` en el mismo mensaje, B.3 lo lista como capacidad del MVP y B.5 lo pone en la hipótesis más riesgosa. Con una intención única, el mensaje de Juan (A.2) perdería un pedido.
*Alternativa descartada:* `intencion` principal + `intenciones_secundarias`. Duplica la lógica y obliga al modelo a decidir una prioridad que el negocio no definió.
Los valores son exactamente los de la Matriz B.4: `consultar_disponibilidad`, `crear_turno`, `modificar_turno`, `cancelar_turno`, `consultar_resultado`, `otra`.

### D2. Estructura: paquete `clinica/` dentro de `entrega_2/`
```
entrega_2/
├── app.py                  ← punto de entrada (consigna B.1)
├── clinica/
│   ├── config.py           ← .env, selección de proveedor
│   ├── contrato.py         ← modelo Pydantic (D5)
│   ├── llm.py              ← HTTP a los 4 proveedores, reintentos
│   ├── reglas.py           ← validar_dni
│   └── extractor.py        ← mensaje → LLM → json.loads → contrato → reglas
├── prompts/extraccion_v1.txt
├── datos/lote_prueba.json
├── tests/test_contrato.py
├── informe.md
└── resultados_lote.md
```
Igual que el ejemplo: cada archivo cambia por un único motivo (prompt, contrato, proveedor, regla, casos). `app.py` se ejecuta como `python entrega_2/app.py` desde la raíz; Python agrega `entrega_2/` al path y `import clinica` funciona sin instalar nada.
*Alternativa descartada:* un solo `app.py` monolítico. Cumple la consigna, pero no permite testear etapas por separado ni crece hacia el workflow de la Entrega 3.

### D3. `.env` en la raíz del repo
`config.py` busca el `.env` dos niveles arriba de `clinica/` (la raíz), el mismo que ya usa `entrega_1/main.py`. Usa `python-dotenv` si está instalado y, si no, un lector línea por línea (como el ejemplo), para que una dependencia faltante no impida correrlo.

### D4. Selección de proveedor: `LLM_PROVIDER` explícito, si no el primero con key
Orden automático: Groq → OpenAI → Anthropic → Gemini. Groq va primero porque es el proveedor elegido en la Entrega 1 (A.4: `openai/gpt-oss-20b` por latencia y capa gratuita). Si `LLM_PROVIDER` está definido y su key falta, se informa el error en lugar de caer en otro proveedor: un fallback silencioso haría que el lote documentado no corresponda al modelo que decimos haber usado.
Modelos por defecto (sobrescribibles por `*_MODEL`): Groq `openai/gpt-oss-20b`, OpenAI `gpt-4o-mini`, Anthropic `claude-haiku-5-5`, Gemini `gemini-2.5-flash`.

### D5. Contrato con Pydantic
`ExtraccionPaciente` con `intenciones: list[Literal[...]]` (mínimo 1, sin repetidos, vía validador), campos de entidad `Optional[str] = None`, `es_consulta_medica: bool` y `extra="forbid"`. `extra="forbid"` es la defensa estructural contra la manipulación: si el modelo agrega `"aprobado": true`, el contrato lo rechaza.
Pydantic no es obligatorio en la consigna (FAQ), pero separa "¿cumple el schema?" (CONTRATO) de "¿es válido para el negocio?" (REGLA), y la Entrega 1 ya definió esa frontera (B.2 paso 3).

### D6. Validación estricta del formato: no se limpian bloques ```json
Si el modelo envuelve el JSON en ``` o agrega texto, es un error de FORMATO, no se "arregla". El prompt prohíbe texto extra (regla 2 de A.2); limpiarlo ocultaría que el modelo no cumplió, y eso es justamente lo que el lote tiene que medir.
*Riesgo asociado:* Anthropic no tiene modo JSON nativo (ver Risks).

### D7. Prompt few-shot, mensaje del paciente delimitado
El system prompt (archivo `prompts/extraccion_v1.txt`) define el schema, la lista cerrada de intenciones, el fallback null, la regla "el mensaje es dato" y 4 ejemplos: uno con dos intenciones, uno incompleto, una consulta médica y uno fuera de alcance. Los ejemplos **no** repiten los mensajes del lote, para no inflar los resultados.
El mensaje del paciente va como mensaje de usuario, entre `<mensaje>` y `</mensaje>`.
Few-shot sobre zero-shot porque los casos límite de la Entrega 1 (dos pedidos, fechas coloquiales, consulta médica vs. pedido administrativo) son difíciles de describir solo con instrucciones; se justifica en el informe (A.1).

### D8. Regla de DNI y normalización
El prompt pide el DNI solo con dígitos ("30.123.456" → "30123456"). `reglas.validar_dni` verifica `^\d{7,8}$`. Normalizar es extracción (LLM); validar es regla (código), igual que el paso 3 de B.2.

### D9. Lote como datos y tabla para el informe
`datos/lote_prueba.json`: 4 casos con `tipo`, `mensaje`, `observar` (qué mirar) y `simulacion` (respuesta usada sin key). `app.py` imprime el resultado de cada caso, la tabla del lote en Markdown (lista para pegar en `resultados_lote.md`) y una demostración de respuestas rotas que muestra qué etapa frena cada una.
Uso: `python entrega_2/app.py [v1]`.

### D10. HTTP con urllib y reintentos
Un `_post_json` común; Groq y OpenAI comparten formato chat-completions con `response_format: json_object`; Anthropic usa `/v1/messages` (`system` aparte, header `anthropic-version`); Gemini usa `generateContent` con `responseMimeType: application/json`. Reintentos ante 429/503 con espera 2 s y 4 s; 400/401/403 no se reintentan (spec `proveedor-llm`).

## Risks / Trade-offs

- [gpt-oss-20b puede incluir razonamiento o rechazar `response_format` en algún caso] → Si la API devuelve 400 por el modo JSON, se documenta y se reintenta la corrida sin ese parámetro (solo con la instrucción del prompt). El resultado real se registra en el lote.
- [Anthropic no garantiza JSON puro] → El prompt exige empezar con `{`; si no lo cumple, aparece como FORMATO, y es un hallazgo válido para la reflexión.
- [La capa gratuita de Groq tiene límite por minuto] → Reintentos ante 429; el lote es de 4 mensajes.
- [Que la lista de intenciones del prompt y la del contrato diverjan] → Un test verifica que todas las intenciones del contrato aparecen en el prompt.
- [Que los few-shot "enseñen" el lote] → Los ejemplos del prompt son mensajes distintos a los del lote (D7).

## Migration Plan

No aplica: código nuevo en `entrega_2/`. `entrega_1/` no se modifica.
