# proveedor-llm Specification

## Purpose

Permite que el sistema llame a un modelo de lenguaje real elegido por configuración, sin que el resto del componente dependa del proveedor y sin que ninguna credencial quede en el código.

## Requirements

### Requirement: Credenciales solo desde el entorno
El sistema MUST leer las API keys de variables de entorno cargadas desde un archivo `.env` en la raíz del repositorio, que está ignorado por git. El repositorio SHALL incluir un `.env.example` con los nombres de las variables y sin valores reales.

#### Scenario: Key configurada en .env
- **WHEN** el `.env` contiene `GROQ_API_KEY` con un valor real
- **THEN** el sistema usa esa key para llamar a Groq

#### Scenario: Placeholder del .env.example
- **WHEN** la variable contiene el texto de ejemplo del `.env.example` (por ejemplo `tu_api_key_de_groq_aqui`)
- **THEN** el sistema la considera no configurada

### Requirement: Proveedores soportados
El sistema SHALL poder llamar a Groq, OpenAI, Anthropic y Gemini, y MUST pedir a cada uno una respuesta en JSON con temperatura 0. El modelo de cada proveedor SHALL poder cambiarse por variable de entorno, con un valor por defecto.

#### Scenario: Groq con el modelo del grupo
- **WHEN** el proveedor elegido es Groq y no se define `GROQ_MODEL`
- **THEN** el sistema usa el modelo `openai/gpt-oss-20b`

#### Scenario: Cambio de proveedor sin tocar código
- **WHEN** el `.env` define `LLM_PROVIDER=anthropic` y `ANTHROPIC_API_KEY`
- **THEN** el sistema llama a Anthropic sin modificar ningún archivo de código

### Requirement: Selección del proveedor
Si `LLM_PROVIDER` está definida, el sistema SHALL usar ese proveedor y MUST informar un error claro si su key no está configurada. Si no está definida, SHALL usar el primer proveedor con key válida, en el orden Groq, OpenAI, Anthropic, Gemini.

#### Scenario: Proveedor explícito sin key
- **WHEN** `LLM_PROVIDER=gemini` y no hay `GEMINI_API_KEY`
- **THEN** el sistema informa que falta la key de Gemini y no cae silenciosamente en otro proveedor

#### Scenario: Selección automática
- **WHEN** `LLM_PROVIDER` no está definida y solo hay `OPENAI_API_KEY`
- **THEN** el sistema usa OpenAI

### Requirement: Modo simulación sin credenciales
Si no hay ningún proveedor configurado, el sistema SHALL procesar el lote con respuestas simuladas predefinidas, indicar en cada resultado que el origen es una simulación y avisar al final cómo configurar una key.

#### Scenario: Sin .env
- **WHEN** se ejecuta el script sin `.env` ni variables de entorno de API
- **THEN** el lote se procesa completo en modo simulación y cada resultado tiene un origen que dice "SIMULACIÓN"

### Requirement: Reintentos ante saturación
Ante una respuesta HTTP 429 o 503, el sistema SHALL reintentar hasta 3 veces con espera creciente. Ante errores de autenticación o de pedido (400, 401, 403) MUST NOT reintentar.

#### Scenario: Límite de uso transitorio
- **WHEN** la primera llamada devuelve 429 y la segunda responde bien
- **THEN** el sistema devuelve la respuesta de la segunda llamada

#### Scenario: Key inválida
- **WHEN** la API devuelve 401
- **THEN** el sistema no reintenta y el error se informa como COMUNICACION
