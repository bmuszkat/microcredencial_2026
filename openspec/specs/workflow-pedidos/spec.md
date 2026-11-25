# workflow-pedidos Specification

## Purpose
Procesa de punta a punta el mensaje de un paciente: lo interpreta con el LLM, lo valida contra los datos de la clínica con reglas en código y lo deja en un estado explícito (resuelto, a la espera del paciente o en manos de una persona), sin ejecutar nunca una operación sobre la agenda.

## Requirements

### Requirement: Pasos encadenados con traza
El workflow SHALL procesar cada mensaje en pasos en secuencia y registrar una traza con un registro por paso ejecutado: número, nombre, tipo (Regla, LLM o Sensor) y resultado. Un paso que no se ejecuta porque el flujo se detuvo antes MUST NOT figurar en la traza.

#### Scenario: Traza de un caso que se completa
- **WHEN** el mensaje "¿Hay lugar el viernes a la mañana?" termina en `COMPLETADO`
- **THEN** la traza incluye pasos de tipo LLM (extracción y redacción) y de tipo Regla y Sensor, cada uno con su resultado

#### Scenario: Traza de un caso que se detiene
- **WHEN** el flujo se detiene en la identificación del paciente
- **THEN** la traza termina en ese paso y no contiene los pasos de redacción ni de verificación del texto

### Requirement: Anonimización del DNI antes del LLM
Antes de llamar al LLM, el workflow MUST detectar con código el DNI del mensaje (7 u 8 dígitos, con o sin puntos), reemplazarlo por `[DNI]` en el texto que se envía y guardarlo. El DNI que el LLM devuelva MUST descartarse y reemplazarse por el detectado por el código.

#### Scenario: Mensaje con DNI
- **WHEN** el mensaje contiene "DNI 30.123.456"
- **THEN** el texto enviado al LLM contiene `[DNI]` y no contiene "30.123.456" ni "30123456", y la extracción validada tiene `dni: "30123456"`

#### Scenario: El LLM devuelve otro valor de DNI
- **WHEN** el código detectó `30123456` y el LLM devuelve `dni: "[DNI]"` o `dni: null`
- **THEN** la extracción validada tiene `dni: "30123456"`

#### Scenario: Más de un candidato a DNI
- **WHEN** el mensaje contiene dos números distintos de 7 u 8 dígitos
- **THEN** el workflow no elige ninguno y termina en `PENDIENTE`, pidiéndole al paciente que indique su DNI

### Requirement: Validación del contrato y del DNI
El workflow SHALL validar la respuesta del LLM contra el contrato de extracción vigente y el formato del DNI repuesto. Si la extracción falla por COMUNICACION, FORMATO o CONTRATO, o el DNI es inválido, MUST terminar en `REVISION_HUMANA` indicando el paso y el motivo.

#### Scenario: Respuesta con una clave fuera del contrato
- **WHEN** el LLM devuelve un JSON con `"aprobado": true`
- **THEN** el workflow termina en `REVISION_HUMANA` con un motivo de tipo CONTRATO, sin ejecutar los pasos siguientes

#### Scenario: El LLM no responde
- **WHEN** la llamada al LLM falla por red o por límite de uso agotado
- **THEN** el workflow termina en `REVISION_HUMANA` con un motivo de tipo COMUNICACION y el programa no se interrumpe

### Requirement: Una resolución por intención
El workflow SHALL resolver por separado cada intención del mensaje y asignarle su propio estado. `consulta_medica` MUST terminar en `DERIVADO` sin que el asistente opine. `otra` MUST terminar en `COMPLETADO` con una respuesta fija y `motivo: "fuera_de_alcance"`, para distinguirla de un pedido resuelto.

#### Scenario: Dos pedidos administrativos
- **WHEN** el mensaje pide reprogramar un turno y consultar un resultado
- **THEN** el workflow resuelve las dos intenciones y el resultado incluye el estado de cada una

#### Scenario: Turno nuevo con un síntoma
- **WHEN** las intenciones son `["crear_turno", "consulta_medica"]`
- **THEN** el pedido de turno se resuelve, `consulta_medica` queda en `DERIVADO` y la respuesta le avisa al paciente que una persona va a responder la parte médica

#### Scenario: Fuera de alcance
- **WHEN** las intenciones son `["otra"]`
- **THEN** el workflow termina en `COMPLETADO` con una respuesta fija, sin llamar al LLM redactor, y la intención registra `motivo: "fuera_de_alcance"`

### Requirement: Pedido contradictorio
Si el mensaje pide a la vez `modificar_turno` y `cancelar_turno`, el workflow MUST NOT resolver ninguna de las dos y SHALL terminar en `PENDIENTE`, preguntándole al paciente qué prefiere.

#### Scenario: Duda entre reprogramar y cancelar
- **WHEN** las intenciones son `["modificar_turno", "cancelar_turno"]`
- **THEN** ambas quedan en `PENDIENTE` con la pregunta "¿preferís reprogramarlo o cancelarlo?"

### Requirement: Identificación del paciente solo cuando hace falta
`crear_turno`, `modificar_turno`, `cancelar_turno` y `consultar_resultado` MUST identificar al paciente por su DNI en el padrón. Sin DNI, el workflow SHALL terminar en `PENDIENTE` y pedírselo. Si el DNI no está en el padrón, MUST terminar en `REVISION_HUMANA`. `consultar_disponibilidad` MUST NOT requerir identificación.

#### Scenario: Pedido sin DNI
- **WHEN** el mensaje es "quiero cambiar el turno" y no trae DNI
- **THEN** el workflow termina en `PENDIENTE` y la respuesta le pide el DNI al paciente

#### Scenario: DNI que no está en el padrón
- **WHEN** el mensaje trae un DNI con formato válido que no figura en el padrón
- **THEN** el workflow termina en `REVISION_HUMANA` con el motivo "DNI no registrado"

#### Scenario: Disponibilidad sin DNI
- **WHEN** el mensaje es "¿hay lugar el viernes a la mañana?" sin DNI
- **THEN** el workflow consulta la agenda sin pasar por el padrón y puede terminar en `COMPLETADO`

### Requirement: Conversión de fechas relativas con código
El workflow SHALL convertir las fechas literales extraídas (día de la semana, "hoy", "mañana", "pasado mañana", "la semana que viene", "dd/mm") en una fecha o rango de calendario y una franja horaria ("a la mañana" 08:00–13:00, "a la tarde" 13:00–19:00), tomando como hoy la fecha de referencia del sistema. Si una fecha necesaria no se entiende, la intención MUST quedar en `PENDIENTE`.

#### Scenario: Día de la semana con franja
- **WHEN** la fecha de referencia es el martes 24/11/2026 y la fecha deseada es "viernes a la mañana"
- **THEN** se convierte en el viernes 27/11/2026 entre las 08:00 y las 13:00

#### Scenario: Fecha que no se entiende
- **WHEN** la fecha deseada es "cuando pueda" y la intención es `modificar_turno`
- **THEN** la intención queda en `PENDIENTE` con la pregunta de qué día prefiere

### Requirement: Verificación contra la agenda
Por cada intención, el workflow SHALL verificar los datos contra el backend. Para modificar o cancelar, el turno mencionado tiene que ser exactamente uno de los turnos futuros del paciente. Para consultar un resultado, el estudio tiene que estar registrado. Para crear, modificar o consultar disponibilidad, se buscan turnos libres en la fecha y franja pedidas. Como la identidad se valida solo con el DNI, las preguntas al paciente MUST NOT mostrar sus turnos ni estudios registrados.

#### Scenario: Turno identificado
- **WHEN** el paciente tiene un único turno futuro, el jueves a las 15:00 con la Dra. López, y menciona "el jueves a las 15 hs con la Dra. López"
- **THEN** ese turno queda identificado como el turno a reprogramar

#### Scenario: Turno que no coincide con la agenda
- **WHEN** el paciente menciona un turno del miércoles y su único turno es un martes
- **THEN** la intención termina en `REVISION_HUMANA` con el motivo de que el turno no coincide

#### Scenario: Dos turnos posibles
- **WHEN** el paciente tiene dos turnos futuros con la misma profesional y no dice cuál
- **THEN** la intención queda en `PENDIENTE` preguntando qué día era el turno, sin mostrar los turnos registrados

#### Scenario: Sin turnos libres en la franja
- **WHEN** no hay turnos libres en la franja pedida para reprogramar
- **THEN** la intención queda en `PENDIENTE` y la respuesta ofrece hasta 3 turnos libres cercanos de la agenda

### Requirement: Cargo por reprogramar o cancelar con poca anticipación
Solo para `modificar_turno` y `cancelar_turno`, el workflow SHALL calcular con código el cargo de la política vigente cuando faltan menos de 24 horas para el turno, medidas desde la fecha y hora de referencia. Con 24 horas o más, el cargo es cero.

#### Scenario: Turno al día siguiente
- **WHEN** son las 10:00 del 24/11 y el turno a reprogramar es el 25/11 a las 09:00
- **THEN** corresponde el cargo de la política, y el monto aparece en los datos validados

#### Scenario: Turno con más de 24 horas
- **WHEN** son las 10:00 del 24/11 y el turno es el 26/11 a las 15:00
- **THEN** el cargo es cero

### Requirement: Las operaciones que escriben esperan confirmación
El workflow MUST NOT crear, modificar ni cancelar turnos. Cuando una de esas intenciones supera todas las validaciones, SHALL terminar en `PENDIENTE_CONFIRMACION`, con la operación propuesta y la pregunta de confirmación para el paciente.

#### Scenario: Reprogramación válida
- **WHEN** el turno se identificó y hay turnos libres el viernes a la mañana
- **THEN** la intención queda en `PENDIENTE_CONFIRMACION` con las opciones ofrecidas y la agenda no se modifica

### Requirement: Estado global por prioridad
El estado global del mensaje SHALL ser el más restrictivo entre los de sus intenciones, en este orden: `REVISION_HUMANA` > `PENDIENTE` > `PENDIENTE_CONFIRMACION` > `DERIVADO` > `COMPLETADO`. Un paso de mensaje que falla (extracción, validación o identificación) MUST definir el estado de todo el mensaje.

#### Scenario: Reprogramación y resultado
- **WHEN** `modificar_turno` queda en `PENDIENTE_CONFIRMACION` y `consultar_resultado` en `COMPLETADO`
- **THEN** el estado global es `PENDIENTE_CONFIRMACION`

#### Scenario: DNI fuera del padrón con dos pedidos
- **WHEN** el mensaje trae dos intenciones que requieren identificación y el DNI no está en el padrón
- **THEN** el estado global es `REVISION_HUMANA` y ninguna intención se resuelve

### Requirement: Resultados reproducibles
El workflow SHALL tomar la fecha y hora de "ahora" de la fecha de referencia configurada en los datos, no del reloj del sistema, para que los casos de prueba y la evidencia den lo mismo cualquier día.

#### Scenario: Correr el lote otro día
- **WHEN** el lote se corre un día distinto al de la evidencia
- **THEN** las fechas convertidas, los cargos y los estados son los mismos
