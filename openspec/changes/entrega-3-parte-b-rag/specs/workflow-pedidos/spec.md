## MODIFIED Requirements

### Requirement: Una resolución por intención
El workflow SHALL resolver por separado cada intención del mensaje y asignarle su propio estado. `consulta_medica` MUST terminar en `DERIVADO` sin que el asistente opine. `otra` MUST pasar por el RAG y registrar un `motivo` que distinga el resultado: `"rag"` (respondida con documentos oficiales, `COMPLETADO`), `"sin_informacion_oficial"` (ningún documento supera el umbral, `COMPLETADO` con el fallback y la derivación a recepción) o `"rag_no_verificado"` (el LLM falló o la respuesta no pasó el guardrail, `REVISION_HUMANA`).

#### Scenario: Dos pedidos administrativos
- **WHEN** el mensaje pide reprogramar un turno y consultar un resultado
- **THEN** el workflow resuelve las dos intenciones y el resultado incluye el estado de cada una

#### Scenario: Turno nuevo con un síntoma
- **WHEN** las intenciones son `["crear_turno", "consulta_medica"]`
- **THEN** el pedido de turno se resuelve, `consulta_medica` queda en `DERIVADO` y la respuesta le avisa al paciente que una persona va a responder la parte médica

#### Scenario: Pregunta informativa respondida con el corpus
- **WHEN** las intenciones son `["otra"]` y el mensaje es "¿qué tengo que hacer antes de un fondo de ojo?"
- **THEN** el workflow termina en `COMPLETADO`, la intención registra `motivo: "rag"` y los documentos citados, y la traza incluye la búsqueda en el corpus (Sensor), la respuesta (LLM) y la verificación de citas y montos (Regla)

#### Scenario: Fuera de alcance
- **WHEN** las intenciones son `["otra"]` y el mensaje es "¿atienden a domicilio?", que no está en el corpus
- **THEN** el workflow termina en `COMPLETADO` con `motivo: "sin_informacion_oficial"`, la respuesta es el fallback con la derivación a recepción y no se llama al LLM después de la extracción

#### Scenario: Respuesta del RAG no verificada
- **WHEN** las intenciones son `["otra"]` y la respuesta del RAG cita un documento que no se recuperó
- **THEN** el workflow termina en `REVISION_HUMANA` con `motivo: "rag_no_verificado"` y el paciente recibe el acuse fijo
