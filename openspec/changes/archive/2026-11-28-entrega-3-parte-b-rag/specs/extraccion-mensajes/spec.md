## MODIFIED Requirements

### Requirement: Detección de consulta médica
El sistema SHALL clasificar como `consulta_medica` todo pedido de opinión clínica (síntomas, gravedad, diagnóstico, medicación, interpretación de resultados), distinguiéndolo de `otra`. Si el mensaje además trae un pedido administrativo, ambas intenciones MUST aparecer. Desde el prompt `v4`, una pregunta sobre una indicación general publicada por la clínica (preparación de un estudio, qué llevar), sin síntomas ni pedido de opinión sobre su caso, SHALL clasificarse como `otra`.

#### Scenario: Síntoma sin pedido administrativo
- **WHEN** el paciente escribe "me arde mucho el ojo desde ayer, ¿es grave?"
- **THEN** `intenciones` es `["consulta_medica"]`

#### Scenario: Síntoma con pedido de turno
- **WHEN** el paciente escribe "veo una mancha negra que se mueve, ¿es grave? Quiero un turno con la Dra. Paz"
- **THEN** `intenciones` contiene `crear_turno` y `consulta_medica`, y no contiene `otra`

#### Scenario: Mensaje incomprensible
- **WHEN** el mensaje es "asdkjh 123 ???"
- **THEN** `intenciones` es `["otra"]`, no `["consulta_medica"]`

#### Scenario: Indicación de preparación publicada (v4)
- **WHEN** con el prompt `v4` el paciente escribe "¿puedo ir manejando al fondo de ojo?"
- **THEN** `intenciones` es `["otra"]`

#### Scenario: Síntoma después de un estudio (v4)
- **WHEN** con el prompt `v4` el paciente escribe "me dilataron ayer y sigo viendo borroso, ¿es normal?"
- **THEN** `intenciones` es `["consulta_medica"]`

### Requirement: Prompt versionado
El system prompt de extracción SHALL vivir en un archivo separado del código, identificado por versión (`v1`, `v2`, `v3`, `v4`, …), y cada resultado MUST indicar qué versión lo generó. Cada versión MUST validarse contra su contrato, para que una versión anterior siga siendo reproducible. El lote de la Entrega 2 SHALL usar `v2` por defecto y el workflow de la Entrega 3, `v4` (mismo contrato que `v2`). El `v3` MUST conservarse sin cambios, para reproducir la corrida de la Parte A.

#### Scenario: Correr con otra versión
- **WHEN** se ejecuta el lote indicando la versión `v1`
- **THEN** el sistema usa el prompt `v1`, valida contra el contrato de `v1` (con `es_consulta_medica` y sin `consulta_medica`) y cada resultado registra `prompt: "v1"`

#### Scenario: Versión por defecto
- **WHEN** se ejecuta el lote sin indicar versión
- **THEN** el sistema usa el prompt `v2` y su contrato

#### Scenario: Versión del workflow
- **WHEN** el workflow de la Entrega 3 extrae un mensaje
- **THEN** usa el prompt `v4`, valida contra el contrato de `v2` y la traza registra `prompt: "v4"`
