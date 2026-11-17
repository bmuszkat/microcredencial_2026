# Proposal

## Why

La Entrega 1 dejó el diseño conceptual del asistente de la clínica: en el paso 2 del user journey, el LLM interpreta el mensaje libre del paciente y lo convierte en una operación estructurada. La Entrega 2 exige demostrar que ese diseño es implementable: un prompt versionado, una llamada real a un modelo y una salida JSON que el sistema pueda procesar. También es la primera prueba de la hipótesis más riesgosa (B.5): que un LLM extrae bien intenciones y entidades de mensajes coloquiales.

## What Changes

- Nuevo componente de **extracción**: recibe un mensaje en texto libre de un paciente y devuelve un JSON con la **lista** de intenciones (valores exactos de la Matriz B.4 de la Entrega 1) y las entidades del mensaje (DNI, profesional, fechas tal como las escribió el paciente, estudio, si es una consulta médica). *(Consigna A.2, B.1.3, B.1.5)*
- **System prompt few-shot versionado** como archivo aparte (`v1`), con schema exacto, sin texto extra, `null` como fallback y la lista cerrada de intenciones. *(Consigna A.1, A.2)*
- **Validación en etapas con errores diferenciados**: comunicación (el modelo no respondió), formato (no es JSON), contrato (es JSON pero no cumple el schema) y regla (un dato no es válido para el negocio, p. ej. DNI). *(Consigna B.1.4, rúbrica criterio 3)*
- **Cliente LLM multi-proveedor** configurado por `.env` (Groq, OpenAI, Anthropic, Gemini), con selección explícita por `LLM_PROVIDER`, reintentos ante saturación y modo simulación sin key. La key nunca está en el código. *(Consigna B.1.1, B.1.2, rúbrica criterio 2)*
- **Script `entrega_2/app.py`** que corre un lote de 4 casos (típico, ambiguo, manipulación, caso límite) y muestra la tabla de resultados. *(Consigna B.1, C.1)*
- **Documentación**: `entrega_2/informe.md` (técnica, prompt, contrato, reflexión), `entrega_2/resultados_lote.md` (tabla del lote real), README con "Cómo correrlo", `requirements.txt` y `.env.example` actualizado. *(Consigna B.2, C.1, C.2, "Qué se entrega")*

### Fuera de alcance

- Convertir fechas relativas ("el jueves") en fechas concretas → **Entrega 3** (regla de calendario, paso 5 del journey).
- Agenda, herramientas (`crear_turno`, `modificar_turno`, etc.) y ejecución de operaciones → **Entrega 3** (workflow encadenado y agente).
- Validar identidad contra un padrón (DNI + fecha de nacimiento) → **Entrega 3**. En esta entrega solo se valida el formato del DNI.
- Redactar la respuesta al paciente (paso 8 del journey) → **Entrega 3**.
- Base de conocimiento / RAG (política de reprogramación, coberturas) → **Entrega 3**.
- Guardrails de salida, matriz de pruebas y ficha de riesgos → **Entrega 4**.

## Capabilities

### New Capabilities

- `extraccion-mensajes`: convertir el mensaje libre de un paciente en una extracción estructurada y validada (intenciones de la Matriz E1 + entidades), con errores diferenciados por etapa y prompt versionado.
- `proveedor-llm`: llamar a un modelo de lenguaje real elegido por configuración (Groq, OpenAI, Anthropic, Gemini), leyendo credenciales del entorno, con reintentos y modo simulación.

### Modified Capabilities

(ninguna: no hay specs previas en el proyecto)

## Impact

- **Código nuevo** en `entrega_2/` (paquete del componente, `app.py`, prompts, datos de prueba, tests). No se modifica `entrega_1/`.
- **Dependencias nuevas**: `pydantic`, `python-dotenv`, `pytest` (declaradas en `requirements.txt` en la raíz).
- **Configuración**: `.env.example` suma `LLM_PROVIDER`, `GROQ_MODEL` y la opción de Anthropic; el `.env` real sigue ignorado.
- **README**: suma la sección "Cómo correrlo" y la estructura de `entrega_2/`.
