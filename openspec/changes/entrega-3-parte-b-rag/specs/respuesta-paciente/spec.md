## MODIFIED Requirements

### Requirement: Quién escribe la respuesta según el estado
La respuesta SHALL redactarla el LLM solo cuando el estado global es `COMPLETADO` o `PENDIENTE_CONFIRMACION` y hay al menos una intención administrativa resuelta. Cuando la única intención es `otra`, la respuesta MUST ser la del RAG: el texto generado con los documentos oficiales o, si no hay información, el fallback con la derivación a recepción. En los demás casos (`PENDIENTE`, `DERIVADO` cuando solo hay una consulta médica y `REVISION_HUMANA`), la respuesta MUST ser una plantilla fija.

#### Scenario: Pedido sin DNI
- **WHEN** el estado global es `PENDIENTE` porque falta el DNI
- **THEN** la respuesta es la plantilla que pide el DNI y no se llama al LLM redactor

#### Scenario: Revisión humana
- **WHEN** el estado global es `REVISION_HUMANA`
- **THEN** la respuesta es un acuse fijo ("recibimos tu mensaje, te responde una persona del equipo"), sin detalles del motivo interno

#### Scenario: Consulta médica sola
- **WHEN** la única intención es `consulta_medica`
- **THEN** la respuesta es la plantilla de derivación y no contiene ninguna opinión clínica

#### Scenario: Pregunta informativa
- **WHEN** la única intención es `otra` y el RAG respondió con documentos oficiales
- **THEN** la respuesta al paciente es el texto del RAG, sin pasar por el LLM redactor de la Parte A
