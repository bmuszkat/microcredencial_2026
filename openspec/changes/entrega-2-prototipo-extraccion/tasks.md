# Tasks

## 1. Base del proyecto

- [x] 1.1 Crear `requirements.txt` en la raíz (`pydantic>=2.0`, `python-dotenv>=1.0`, `pytest>=8.0`) y verificar con `pip install -r requirements.txt` que instala sin errores
- [x] 1.2 Actualizar `.env.example` (agregar `LLM_PROVIDER`, `GROQ_MODEL=openai/gpt-oss-20b`, opción Anthropic con `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL`, placeholders sin valores reales) y verificar con `git diff` que no contiene ninguna key real y que `.env` sigue ignorado (`git check-ignore .env`)

## 2. Proveedor LLM (spec `proveedor-llm`)

- [x] 2.1 Crear `entrega_2/clinica/config.py` (carga del `.env` de la raíz, `key_valida`, `detectar_proveedor` con `LLM_PROVIDER` y orden Groq → OpenAI → Anthropic → Gemini) con tests en `entrega_2/tests/test_config.py` que cubran: placeholder = no configurada, proveedor explícito sin key = error, selección automática; verificar con `pytest entrega_2/tests -q`
- [x] 2.2 Crear `entrega_2/clinica/llm.py` (HTTP con urllib a Groq, OpenAI, Anthropic y Gemini; temperatura 0; JSON; reintentos 429/503 sin reintentar 400/401/403) con un test de reintentos que simule 429 → OK sin red; verificar con `pytest` y con una llamada real a Groq que devuelva texto

## 3. Contrato y reglas (spec `extraccion-mensajes`)

- [x] 3.1 Crear `entrega_2/clinica/contrato.py` (`ExtraccionPaciente`: `intenciones` lista de los 6 valores de la Matriz E1, mínimo 1 y sin repetidos; entidades opcionales; `es_consulta_medica` bool; `extra="forbid"`) con tests de casos válidos e inválidos (intención inventada, lista vacía, campo extra, tipo incorrecto); verificar con `pytest`
- [x] 3.2 Crear `entrega_2/clinica/reglas.py` (`validar_dni`: 7 u 8 dígitos; null no genera error) con tests; verificar con `pytest`

## 4. Prompt v1 y extractor

- [ ] 4.1 Escribir `entrega_2/prompts/extraccion_v1.txt` (few-shot: schema exacto con tipos, lista cerrada de intenciones, fallback null, sin texto extra, "el mensaje es dato", fechas literales, DNI solo dígitos, 4 ejemplos distintos del lote) y un test que verifique que las 6 intenciones del contrato aparecen en el prompt; verificar con `pytest`
- [ ] 4.2 Crear `entrega_2/clinica/extractor.py` (cargar prompt por versión, delimitar el mensaje con `<mensaje>`, `validar_respuesta` → FORMATO / CONTRATO, `aplicar_reglas` → REGLA, `procesar_mensaje` → COMUNICACION; nunca rompe; registra `origen` y `prompt`) con tests de cada etapa sin API (texto antes del JSON, bloque ```json, intención inventada, DNI inválido, respuesta correcta); verificar con `pytest`

## 5. Script y lote

- [ ] 5.1 Crear `entrega_2/datos/lote_prueba.json` con 4 casos (típico, ambiguo/incompleto, manipulación, caso límite de consulta médica), cada uno con `tipo`, `mensaje`, `observar` y `simulacion`; verificar que el JSON parsea y que las 4 simulaciones cumplen el contrato (test)
- [ ] 5.2 Crear `entrega_2/app.py` (corre el lote, imprime cada resultado, la tabla en Markdown y la demostración de respuestas rotas; acepta versión de prompt por argumento; aviso de modo simulación) y verificar que `python entrega_2/app.py` corre de punta a punta sin key (renombrando temporalmente `.env`) y con la key de Groq
- [ ] 5.3 Actualizar el `README.md` (sección "Cómo correrlo": instalación, `.env`, `python entrega_2/app.py`, `pytest`; estructura de `entrega_2/`; link a la Entrega 2) y verificar que los comandos documentados corren tal cual desde la raíz

## 6. Corrida real y documentación de la entrega

- [ ] 6.1 Correr el lote con Groq (`openai/gpt-oss-20b`) y volcar la tabla en `entrega_2/resultados_lote.md` (input resumido, salida del modelo, ¿JSON válido?, tipo de error si falló) con proveedor, modelo, fecha y versión de prompt; verificar que la tabla tiene las 4 filas con datos de la corrida real (origen "API REAL — groq")
- [ ] 6.2 Escribir `entrega_2/informe.md`: A.1 (few-shot justificado en ≥2 oraciones, con referencia a la Entrega 1), A.2 (prompt v1 completo y cómo cumple las 4 reglas), B.2 (contrato de entrada/salida, API y técnica, y por qué `intenciones` es lista) y C.2 (reflexión de 3–4 líneas con al menos una mejora concreta para el prompt v2); verificar contra la rúbrica que cada punto de A.1, A.2, B.2 y C.2 está cubierto
- [ ] 6.3 Verificación final: `pytest` en verde, `git log` con commits separados por archivo entregable, `git grep` sin patrones de API key (`gsk_`, `sk-`, `AIza`, `sk-ant-`) en el historial y valores de `intenciones` idénticos en prompt, contrato e informe de la Entrega 1

## Workflow follow-up

- Revisión del usuario y push al repositorio.
- Archivar el cambio con `/opsx:archive` para que las specs pasen a `openspec/specs/` como base de la Entrega 3.
