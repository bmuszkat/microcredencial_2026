# Spec Delta

## MODIFIED Requirements

### Requirement: Salida en JSON con schema fijo
El sistema SHALL devolver, por cada mensaje, un objeto JSON con exactamente estas claves: `intenciones` (lista de strings), `dni` (string o null), `profesional` (string o null), `fecha_turno_actual` (string o null), `fecha_deseada` (string o null) y `estudio` (string o null).

#### Scenario: Mensaje típico de reprogramación
- **WHEN** el paciente escribe "Soy Juan Pérez, DNI 30123456. Tengo turno el jueves a las 15 con la Dra. López y quiero pasarlo al viernes a la mañana"
- **THEN** la extracción contiene `intenciones: ["modificar_turno"]`, `dni: "30123456"`, `profesional: "Dra. López"`, `fecha_turno_actual: "jueves 15 hs"` y `fecha_deseada: "viernes a la mañana"`

#### Scenario: Respuesta del modelo con claves faltantes o tipos incorrectos
- **WHEN** el modelo devuelve un JSON sin la clave `intenciones`, con una clave que no está en el schema (por ejemplo `es_consulta_medica` o `aprobado`) o con `dni: 30123456` como número
- **THEN** el sistema rechaza la extracción con un error de tipo CONTRATO que indica qué campo falló

### Requirement: Intenciones limitadas a la Matriz de la Entrega 1
Cada elemento de `intenciones` MUST ser uno de estos valores exactos: `consultar_disponibilidad`, `crear_turno`, `modificar_turno`, `cancelar_turno`, `consultar_resultado`, `consulta_medica`, `otra`. La lista MUST tener al menos un elemento y no repetir valores. `otra` MUST NOT combinarse con otras intenciones.

#### Scenario: Mensaje con dos pedidos
- **WHEN** el paciente pide reprogramar un turno y además pregunta si su campo visual está listo
- **THEN** `intenciones` contiene `modificar_turno` y `consultar_resultado`

#### Scenario: Intención inventada por el modelo
- **WHEN** el modelo devuelve `intenciones: ["aprobar_turno_urgente"]`
- **THEN** el sistema rechaza la extracción con un error de tipo CONTRATO

#### Scenario: Mensaje fuera del alcance del MVP
- **WHEN** el paciente pregunta "¿Cuánto sale una consulta particular?"
- **THEN** `intenciones` es `["otra"]`

#### Scenario: `otra` combinada con otra intención
- **WHEN** el modelo devuelve `intenciones: ["crear_turno", "otra"]`
- **THEN** el sistema rechaza la extracción con un error de tipo CONTRATO

### Requirement: Detección de consulta médica
El sistema SHALL clasificar como `consulta_medica` todo pedido de opinión clínica (síntomas, gravedad, diagnóstico, medicación, interpretación de resultados), distinguiéndolo de `otra`. Si el mensaje además trae un pedido administrativo, ambas intenciones MUST aparecer en la lista.

#### Scenario: Síntoma sin pedido administrativo
- **WHEN** el paciente escribe "me arde mucho el ojo desde ayer, ¿es grave?"
- **THEN** `intenciones` es `["consulta_medica"]`

#### Scenario: Síntoma con pedido de turno
- **WHEN** el paciente escribe "veo una mancha negra que se mueve, ¿es grave? Quiero un turno con la Dra. Paz"
- **THEN** `intenciones` contiene `crear_turno` y `consulta_medica`, y no contiene `otra`

#### Scenario: Mensaje incomprensible
- **WHEN** el mensaje es "asdkjh 123 ???"
- **THEN** `intenciones` es `["otra"]`, no `["consulta_medica"]`

### Requirement: Errores diferenciados por etapa
El sistema SHALL informar en qué etapa falló un mensaje, con un tipo y un detalle distintos para cada una: COMUNICACION (el modelo no respondió), FORMATO (el modelo respondió pero no con JSON válido, incluido el caso en que el proveedor rechaza la salida por no ser JSON), CONTRATO (el JSON no cumple el schema) y REGLA (un dato no es válido para el negocio). Ningún error MUST interrumpir el procesamiento de los demás mensajes.

#### Scenario: El modelo agrega texto antes del JSON
- **WHEN** el modelo responde `¡Claro! {"intenciones": ["otra"], ...}`
- **THEN** el sistema informa un error de tipo FORMATO y conserva la respuesta cruda para diagnóstico

#### Scenario: El proveedor rechaza la salida por no ser JSON
- **WHEN** la API devuelve HTTP 400 con código `json_validate_failed`
- **THEN** el sistema informa un error de tipo FORMATO (no COMUNICACION) y conserva como respuesta cruda lo que el modelo generó

#### Scenario: Falla de red o de autenticación
- **WHEN** la API devuelve 401 o no hay conexión
- **THEN** el sistema informa un error de tipo COMUNICACION con el mensaje de la API, distinto del de FORMATO, y sigue con el próximo mensaje

#### Scenario: Input basura
- **WHEN** el mensaje es "asdkjh 123 ???"
- **THEN** el sistema devuelve una extracción válida (típicamente `["otra"]`) o un error tipificado, sin romper el programa

### Requirement: Prompt versionado
El system prompt de extracción SHALL vivir en un archivo separado del código, identificado por versión (`v1`, `v2`, …), y cada resultado MUST indicar qué versión de prompt lo generó. Cada versión MUST validarse contra el contrato que le corresponde, de modo que una versión anterior siga siendo reproducible después de que el contrato evolucione. La versión por defecto SHALL ser la más reciente (`v2`).

#### Scenario: Correr con otra versión
- **WHEN** se ejecuta el lote indicando la versión `v1`
- **THEN** el sistema usa el prompt `v1`, valida contra el contrato de `v1` (con `es_consulta_medica` y sin `consulta_medica`) y cada resultado registra `prompt: "v1"`

#### Scenario: Versión por defecto
- **WHEN** se ejecuta el lote sin indicar versión
- **THEN** el sistema usa el prompt `v2` y su contrato
