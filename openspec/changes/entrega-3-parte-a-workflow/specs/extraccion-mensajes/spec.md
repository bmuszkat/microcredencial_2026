# Spec Delta

## ADDED Requirements

### Requirement: Extracción con el DNI anonimizado
Cuando el mensaje recibido contiene el marcador `[DNI]` en lugar del documento, la extracción SHALL devolver `dni: null` y tratar el marcador como un dato ya resuelto por el sistema, sin inventar un número.

#### Scenario: Mensaje anonimizado
- **WHEN** el mensaje es "Soy Juan, DNI [DNI]. ¿Está mi campo visual?"
- **THEN** la extracción tiene `dni: null`, `intenciones: ["consultar_resultado"]` y `estudio` con "campo visual"

### Requirement: La fecha de un estudio no es la de un turno
La extracción MUST NOT poner la fecha en que el paciente se hizo un estudio en `fecha_turno_actual` ni en `fecha_deseada`. Esos campos son solo para turnos.

#### Scenario: Consulta de resultado con fecha del estudio
- **WHEN** el paciente escribe "¿ya están los resultados de la OCT que me hice el jueves?"
- **THEN** `fecha_turno_actual` y `fecha_deseada` son `null` y `estudio` contiene "OCT"

### Requirement: El profesional es solo quien atiende
`profesional` SHALL contener únicamente el nombre de un profesional de la clínica tal como lo escribe el paciente. MUST ser `null` si el mensaje solo nombra a un paciente o a quien escribe, o si menciona al profesional sin nombre ("el doctor que me operó").

#### Scenario: Nombre de un paciente
- **WHEN** el mensaje dice "confirmá el turno del Sr. Pérez del viernes"
- **THEN** `profesional` es `null`

#### Scenario: Profesional sin nombre
- **WHEN** el mensaje dice "necesito un control con el doctor que me operó"
- **THEN** `profesional` es `null`

## MODIFIED Requirements

### Requirement: Prompt versionado
El system prompt de extracción SHALL vivir en un archivo separado del código, identificado por versión (`v1`, `v2`, `v3`, …), y cada resultado MUST indicar qué versión de prompt lo generó. Cada versión MUST validarse contra el contrato que le corresponde, de modo que una versión anterior siga siendo reproducible después de que el contrato evolucione. El lote de la Entrega 2 SHALL usar `v2` por defecto, y el workflow de la Entrega 3 SHALL usar `v3`, que valida contra el mismo contrato que `v2`.

#### Scenario: Correr con otra versión
- **WHEN** se ejecuta el lote indicando la versión `v1`
- **THEN** el sistema usa el prompt `v1`, valida contra el contrato de `v1` (con `es_consulta_medica` y sin `consulta_medica`) y cada resultado registra `prompt: "v1"`

#### Scenario: Versión por defecto
- **WHEN** se ejecuta el lote sin indicar versión
- **THEN** el sistema usa el prompt `v2` y su contrato

#### Scenario: Versión del workflow
- **WHEN** el workflow de la Entrega 3 extrae un mensaje
- **THEN** usa el prompt `v3`, valida contra el contrato de `v2` y la traza registra `prompt: "v3"`
