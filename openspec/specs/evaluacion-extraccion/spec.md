# evaluacion-extraccion Specification

## Purpose

Mide cuán bien el componente de extracción interpreta mensajes reales de pacientes, comparando sus salidas contra respuestas esperadas escritas de antemano, para validar la hipótesis más riesgosa de la Entrega 1 (≥ 90 %) y comparar versiones de prompt.

## Requirements

### Requirement: Set de evaluación etiquetado de antemano
El sistema SHALL contar con un set de al menos 50 mensajes de pacientes, cada uno con su resultado esperado (intenciones y entidades `dni`, `profesional`, `fecha_turno_actual`, `fecha_deseada`, `estudio`) escrito antes de correr el modelo. Ningún mensaje del set MUST coincidir con un ejemplo de los prompts.

#### Scenario: Composición del set
- **WHEN** se revisa el set de evaluación
- **THEN** incluye mensajes simples, con varios pedidos, ambiguos o incompletos, consultas médicas (solas y mezcladas con turnos), fuera de alcance y de manipulación, y cada intención de la Matriz aparece en al menos 3 mensajes

#### Scenario: Etiquetas válidas
- **WHEN** se cargan las respuestas esperadas
- **THEN** todas usan solo intenciones de la Matriz vigente y respetan las reglas del contrato vigente (por ejemplo, `otra` sola)

### Requirement: Métricas de la evaluación
Al evaluar una versión de prompt, el sistema SHALL informar: porcentaje de respuestas con JSON válido, porcentaje que cumple el contrato, porcentaje de mensajes con las intenciones exactamente correctas, porcentaje de entidades correctas y porcentaje de mensajes completamente correctos (intenciones y todas las entidades), junto con la lista de mensajes que fallaron y por qué.

#### Scenario: Comparación de intenciones
- **WHEN** el esperado es `["modificar_turno", "consultar_resultado"]` y el modelo devuelve `["consultar_resultado", "modificar_turno"]`
- **THEN** cuenta como intenciones correctas (el orden no importa)

#### Scenario: Comparación de entidades
- **WHEN** la entidad esperada es `null`
- **THEN** solo es correcta si el modelo devolvió `null`; si la esperada es un texto, es correcta si el valor del modelo lo contiene, sin distinguir mayúsculas ni tildes

#### Scenario: Respuesta que no llega a evaluarse
- **WHEN** un mensaje termina en error de COMUNICACION, FORMATO o CONTRATO
- **THEN** cuenta como incorrecto en intenciones y entidades, y el error aparece en la lista de fallos

### Requirement: Comparación entre versiones de prompt
El sistema SHALL poder evaluar cualquier versión de prompt existente sobre el mismo set. Las salidas de versiones con otro contrato MUST normalizarse al espacio de intenciones vigente antes de compararlas (en `v1`, `otra` con `es_consulta_medica: true` equivale a `consulta_medica`).

#### Scenario: Evaluar v1 con el set vigente
- **WHEN** `v1` devuelve `["otra"]` con `es_consulta_medica: true` y el esperado es `["consulta_medica"]`
- **THEN** cuenta como intenciones correctas

### Requirement: Evaluación tolerante a límites de uso
La evaluación SHALL guardar cada resultado a medida que lo obtiene, poder retomarse sin repetir llamadas ya hechas y espaciar las llamadas para no superar el límite de la API. Ningún error de un mensaje MUST cortar la evaluación de los demás.

#### Scenario: Corrida interrumpida
- **WHEN** la evaluación se corta en el mensaje 30 y se vuelve a ejecutar
- **THEN** retoma desde el mensaje 31 usando los resultados ya guardados

#### Scenario: Límite de uso
- **WHEN** la API devuelve 429 repetidamente en un mensaje y se agotan los reintentos
- **THEN** ese mensaje queda registrado como COMUNICACION y la evaluación continúa
