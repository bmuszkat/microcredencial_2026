# Proposal

## Why

El componente de la Entrega 2 convierte un mensaje en un JSON validado, pero se queda ahí: no sabe si el paciente existe, si el turno que menciona está en la agenda, si hay lugar el viernes ni si le corresponde un cargo. Por eso todavía no puede contestarle al paciente. La Parte A de la Entrega 3 pide encadenar esa extracción en un **workflow ejecutable** con validación en código y puntos de control (Clase 4, Hito 1). Lo armamos siguiendo el user journey B.2 de la Entrega 1, que ya separaba qué pasos son del LLM y cuáles son reglas.

## What Changes

- **Workflow de 12 pasos** en `entrega_3/workflow.py`. Cubre el journey B.2 de la Entrega 1 desde la recepción hasta la respuesta: anonimizar el DNI, extraer, validar, enrutar por intención, identificar al paciente, convertir fechas, verificar contra la agenda, calcular el cargo, pedir confirmación, redactar y verificar el texto. *(Consigna A.1: al menos 3 pasos, una validación en código con lógica del dominio y un punto de control.)*
- **Varios puntos de control con estados explícitos.** Los estados son `REVISION_HUMANA`, `PENDIENTE`, `PENDIENTE_CONFIRMACION`, `DERIVADO` y `COMPLETADO`, con un criterio único para separar "el paciente lo resuelve contestando" (`PENDIENTE`) de "el sistema no puede confiar en lo que recibió" (`REVISION_HUMANA`). *(A.1, A.3.)*
- **Varias intenciones por mensaje.** Se resuelve cada intención administrativa por separado. Una consulta médica se deriva a una persona sin frenar el resto, y el estado global es el más restrictivo. *(A.1. Es el caso principal de la Entrega 1: Juan trae dos pedidos.)*
- **Anonimización del DNI** antes de llamar al LLM. El DNI lo detecta y lo pone el código: el modelo nunca lo ve. *(Implementa la opción elegida en la sección de privacidad de la Entrega 2.)*
- **Prompt de extracción v3** en `entrega_3/prompts/`. Es el v2 más el manejo de `[DNI]` y los dos errores que encontró la evaluación de la Entrega 2: la fecha de un estudio no es un turno (s12) y un paciente no es un profesional (p02). *(A.1, paso 1: "reusar o mejorar el prompt de la E2".)*
- **Datos ficticios del backend** (padrón, agenda, estudios y política de cargos) y **sensores de solo lectura** sobre ellos. Son la "autoridad" contra la que se valida, y la Parte C los va a reutilizar como herramientas del agente. *(A.1, paso 2.)*
- **Redacción con datos validados, plantillas y guardrail.** El LLM redacta solo con los datos que el código validó. Si la API falla se usa una plantilla. Cada horario, fecha y monto del texto se compara con los datos, y si alguno no coincide se reemplaza todo por la plantilla. *(A.1, paso 4. Es el paso 9 del journey B.2, que responde a la alucinación documentada en A.2 de la Entrega 1.)*
- **Lote de 9 casos con el estado esperado fijado antes de correr** (incluye uno de manipulación), corrida real contra Groq, diagrama Mermaid e informe. *(A.2 y A.3.)*

### Fuera de alcance

- **Ejecutar operaciones en la agenda** (pasos 10 a 13 del journey: interpretar la elección del paciente, recibir el "SÍ", escribir el turno y enviar el comprobante). El workflow termina en `PENDIENTE_CONFIRMACION` y nunca escribe → **Entrega 4** (integración punta a punta).
- **Identidad con DNI y fecha de nacimiento.** Los mensajes casi nunca traen la fecha de nacimiento, así que en el prototipo alcanza con que el DNI esté en el padrón. Es una simplificación declarada → **Entrega 4**.
- **Seudonimizar nombres y síntomas.** Solo se anonimiza el DNI. El análisis completo está en el informe de la Entrega 2 → **Entrega 4** (ficha de riesgos).
- **Reevaluar el prompt v3 sobre los 50 mensajes del set de la Entrega 2.** Con el DNI anonimizado, el set necesita adaptarse → **Entrega 4** (matriz de pruebas).
- **RAG** (políticas, coberturas y preparación de estudios en texto libre) → **Parte B**. **Agente con LangGraph** → **Parte C**.
- **Mover `entrega_2/clinica/` a un paquete común.** Se importa desde `entrega_3` sin modificarlo → **Entrega 4**.

## Capabilities

### New Capabilities

- `workflow-pedidos`: procesar el mensaje de un paciente de punta a punta con pasos encadenados, puntos de control, un estado por intención y un estado global, y una traza de cada paso. *(A.1, A.3)*
- `agenda-clinica`: datos ficticios del backend (padrón, agenda, estudios, política de cargos) y consultas de solo lectura sobre ellos. *(A.1, paso 2. La reutiliza la Parte C.)*
- `respuesta-paciente`: redactar la respuesta con datos validados, las plantillas por estado y el guardrail de horarios, fechas y montos. *(A.1, paso 4)*

### Modified Capabilities

- `extraccion-mensajes`: suma el prompt v3, el manejo del DNI anonimizado y dos reglas de extracción (la fecha de un estudio no es un turno; `profesional` es solo quien atiende).

## Impact

- **Código nuevo, todo en `entrega_3/`:** `workflow.py`, `reglas.py`, `herramientas.py`, `redactor.py`, `prompts/`, `datos/`, `evidencia/`, `tests/`, `conftest.py` e `informe.md`.
- **`entrega_2/` no se modifica.** Se importan `clinica.llm`, `clinica.extractor`, `clinica.contrato` y `clinica.reglas` agregando `entrega_2` al `sys.path`.
- **`README.md` de la raíz:** fila de la Entrega 3 y comandos.
- **Dependencias:** ninguna nueva (pydantic, python-dotenv, pytest).
- **Costo de API:** el lote de 9 casos hace hasta 2 llamadas por caso (extracción y redacción). Con una pausa de 20 s entre llamadas, la corrida tarda unos 7 minutos.
