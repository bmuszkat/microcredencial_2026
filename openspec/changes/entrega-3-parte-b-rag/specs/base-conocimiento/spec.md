# Spec Delta

## Purpose

Convierte el corpus en un índice de búsqueda semántica en español y devuelve, para una pregunta, los documentos vigentes más parecidos junto con su grado de similitud, para que el código decida si hay información suficiente antes de llamar al LLM.

## ADDED Requirements

### Requirement: Índice persistido y reconstruido si cambia el corpus
El sistema SHALL indexar el texto, el `id` y los metadatos de cada documento con un modelo de embeddings local (sin API key) y guardar el índice en disco, fuera del control de versiones. Si el corpus cambió desde la última indexación, el índice MUST reconstruirse; si no cambió, MUST reutilizarse.

#### Scenario: Primera indexación
- **WHEN** no existe el índice y se hace una búsqueda
- **THEN** el sistema indexa todos los documentos del corpus antes de buscar

#### Scenario: Corpus modificado
- **WHEN** se edita un documento del corpus después de indexar
- **THEN** la siguiente búsqueda reconstruye el índice y encuentra el texto nuevo

#### Scenario: Corpus sin cambios
- **WHEN** se busca dos veces sin modificar el corpus
- **THEN** la segunda búsqueda reutiliza el índice sin volver a calcular los embeddings

### Requirement: Recuperación de los k más similares con su similitud
Para una pregunta, el sistema SHALL devolver como máximo k documentos (k=3 por defecto), ordenados de mayor a menor similitud, cada uno con su `id`, su texto, sus metadatos y un valor de similitud entre 0 y 1.

#### Scenario: Pregunta sobre un tema del corpus
- **WHEN** se pregunta "¿me cobran si cancelo el turno a último momento?"
- **THEN** el primer documento recuperado es la política de cargos vigente

#### Scenario: Orden y cantidad
- **WHEN** se hace cualquier búsqueda
- **THEN** se devuelven como máximo k documentos, con la similitud en orden descendente

### Requirement: Filtrado híbrido por metadatos
La búsqueda SHALL combinar la similitud semántica con un filtro exacto por metadatos. Por defecto MUST recuperar solo documentos con `vigente: true`, y SHALL aceptar filtros adicionales (por ejemplo `categoria` u `obra_social`).

#### Scenario: La versión derogada no se recupera
- **WHEN** se pregunta por el cargo de cancelación con el filtro por defecto
- **THEN** ningún documento recuperado tiene `vigente: false`

#### Scenario: Sin filtro la derogada aparece
- **WHEN** se hace la misma pregunta sin filtro de vigencia
- **THEN** la versión derogada aparece entre los recuperados, lo que muestra que el filtro es lo que la excluye

#### Scenario: Filtro por categoría
- **WHEN** se busca con el filtro `categoria: "preparacion_estudio"`
- **THEN** todos los documentos recuperados tienen esa categoría

### Requirement: Umbral de similitud calibrado
El sistema SHALL definir un umbral de similitud fijado con una medición sobre preguntas dentro y fuera del corpus, registrada como evidencia. Un documento por debajo del umbral MUST considerarse no relevante.

#### Scenario: Pregunta fuera del corpus
- **WHEN** se pregunta "¿atienden a domicilio?"
- **THEN** ningún documento recuperado supera el umbral

#### Scenario: Pregunta dentro del corpus
- **WHEN** se pregunta "¿qué tengo que llevar el día del turno?"
- **THEN** al menos un documento supera el umbral
