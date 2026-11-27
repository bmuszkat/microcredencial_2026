# Spec Delta

## Purpose

Responde las preguntas informativas de los pacientes usando únicamente los documentos oficiales recuperados, dice explícitamente cuando no tiene la información y verifica en código que la respuesta no cite ni invente nada fuera de lo recuperado.

## ADDED Requirements

### Requirement: Respuesta solo con los documentos recuperados
Cuando al menos un documento supera el umbral, el sistema SHALL llamar al LLM con los documentos recuperados como contexto y un system prompt que le indique usar ÚNICAMENTE esos fragmentos y responder "No tengo información oficial sobre esa consulta." si no se puede deducir. La respuesta MUST indicar qué documentos usó.

#### Scenario: Pregunta respondida
- **WHEN** se pregunta "¿me cobran si cancelo con menos de 24 horas?"
- **THEN** la respuesta menciona el cargo de la política vigente y cita el `id` de ese documento

#### Scenario: El contexto no alcanza
- **WHEN** los documentos recuperados superan el umbral pero no responden la pregunta
- **THEN** la respuesta es "No tengo información oficial sobre esa consulta."

### Requirement: Fallback sin llamar al LLM
Si ningún documento supera el umbral, el sistema MUST responder "No tengo información oficial sobre esa consulta." sin llamar al LLM, e indicar que la consulta se deriva a recepción.

#### Scenario: Pregunta fuera del corpus
- **WHEN** se pregunta "¿atienden a domicilio?"
- **THEN** la respuesta es el fallback, el resultado indica que no se llamó al LLM y no hay documentos citados

### Requirement: Guardrail de citas y montos
Antes de entregar la respuesta, el código MUST verificar que cada documento citado esté entre los recuperados y que cada monto y porcentaje del texto aparezca en el texto de algún documento recuperado. Si algo no coincide, la respuesta MUST descartarse y el resultado MUST marcarse para revisión humana.

#### Scenario: Cita de un documento no recuperado
- **WHEN** el LLM cita un `id` que no estaba entre los documentos recuperados
- **THEN** la respuesta se descarta y el resultado queda para revisión humana

#### Scenario: Monto inventado
- **WHEN** la respuesta dice "$5.000" y ningún documento recuperado contiene ese monto
- **THEN** la respuesta se descarta y el resultado queda para revisión humana

#### Scenario: Respuesta respaldada
- **WHEN** la respuesta cita solo documentos recuperados y sus montos aparecen en ellos
- **THEN** la respuesta se entrega tal cual

### Requirement: Falla del LLM
Si el LLM no responde, responde fuera del formato esperado o se agotan los reintentos, el sistema MUST NOT inventar una respuesta: el resultado SHALL marcarse para revisión humana con el error registrado.

#### Scenario: Error de comunicación
- **WHEN** la llamada al LLM falla después de los reintentos
- **THEN** el resultado queda para revisión humana y no hay texto generado

### Requirement: Comparación con y sin grounding
El sistema SHALL poder correr un conjunto fijo de preguntas dos veces: sin contexto (el LLM responde de memoria) y con RAG, y mostrar las dos respuestas lado a lado con los documentos usados. Las preguntas y lo que se espera de cada una MUST estar versionadas antes de la corrida real, e incluir al menos una pregunta fuera del corpus.

#### Scenario: Pregunta que en la Entrega 1 se respondió inventando
- **WHEN** se compara "¿me cobran por reprogramar con menos de 24 horas?"
- **THEN** la salida muestra la respuesta sin grounding y la respuesta con RAG, que usa el monto de la política vigente y cita el documento

#### Scenario: Pregunta fuera del corpus
- **WHEN** se compara una pregunta fuera del corpus
- **THEN** la respuesta con RAG es el fallback, mientras que la respuesta sin grounding queda registrada tal como la dio el modelo

### Requirement: Ejecutable sin API key
Sin ninguna API key configurada, la búsqueda SHALL funcionar igual (los embeddings son locales) y la generación MUST usar respuestas simuladas, indicando en la salida que es una simulación.

#### Scenario: Búsqueda sin key
- **WHEN** no hay key y se busca una pregunta
- **THEN** se muestran los documentos recuperados con su similitud y la salida avisa que la generación es simulada
