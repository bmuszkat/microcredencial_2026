# corpus-clinica Specification

## Purpose

Reúne la información oficial de la clínica que no está en la agenda ni en el padrón (políticas, coberturas, preparación de estudios, sedes, documentación), escrita para que la encuentre una búsqueda semántica y con metadatos que permitan filtrarla con exactitud.

## Requirements

### Requirement: Documentos del caso con texto semántico
El corpus SHALL tener entre 10 y 15 documentos sobre la clínica. Cada documento MUST tener un `id` único, un `titulo` y una `descripcion_semantica` que explique el tema con el vocabulario que usaría un paciente (sinónimos y formas de preguntarlo). Ningún documento MUST ser genérico ni un texto de relleno.

#### Scenario: Estructura de cada documento
- **WHEN** se carga el corpus
- **THEN** tiene entre 10 y 15 documentos, los `id` no se repiten y ningún `titulo` ni `descripcion_semantica` está vacío

#### Scenario: Temas que le faltaron al modelo en la Entrega 1
- **WHEN** se revisan las categorías del corpus
- **THEN** hay al menos un documento vigente de cargos por cancelar o reprogramar, uno de cobertura por obra social y uno de preparación de estudios

### Requirement: Metadatos filtrables
Cada documento MUST tener al menos dos metadatos filtrables: `categoria` (de una lista cerrada) y `vigente` (booleano). Los datos exactos (montos, plazos, obra social, sede, versión) SHALL estar en los metadatos cuando sirven para filtrar, y la explicación en el texto.

#### Scenario: Metadatos válidos
- **WHEN** se carga el corpus
- **THEN** cada documento tiene `categoria` dentro de la lista cerrada y `vigente` booleano

#### Scenario: Documento por obra social
- **WHEN** un documento describe la cobertura de una obra social
- **THEN** tiene el metadato `obra_social` con el nombre de esa obra social

### Requirement: Versión derogada de una política
El corpus MUST incluir al menos una política con una versión derogada (`vigente: false`) y su reemplazo vigente sobre el mismo tema, para demostrar que el filtro por metadatos evita responder con información vieja.

#### Scenario: Dos versiones de la política de cargos
- **WHEN** se buscan los documentos de categoría cargos
- **THEN** hay una versión vigente y una derogada, con distinto monto o umbral

### Requirement: Coherencia con los datos del backend
Lo que el corpus vigente diga sobre cargos, profesionales, sedes, obras sociales y estudios MUST coincidir con los datos de la Parte A (política de cargos, agenda, padrón y estudios), para que el RAG y el workflow nunca le digan al paciente cosas distintas.

#### Scenario: Monto del cargo
- **WHEN** se compara la política de cargos vigente del corpus con la política de cargos del backend
- **THEN** el monto y el umbral de horas son los mismos

#### Scenario: Profesionales y sedes
- **WHEN** el corpus menciona un profesional o una sede
- **THEN** ese profesional existe en la agenda con esa especialidad y esa sede
