# Tasks

## 1. Entorno

- [x] 1.1 Crear el `.venv` con `uv venv --python 3.12`, agregar `.python-version` (`3.12`), sumar a `requirements.txt` `langchain-core`, `langchain-openai`, `langchain-chroma` y `fastembed` con versión mínima y comentario (design D1), y agregar `entrega_3/indice_chroma/` al `.gitignore`. Actualizar el README: "Python 3.10 a 3.13" y cómo crear el entorno (con `uv` o con `python -m venv`). Verificar con `pip install -r requirements.txt` dentro del venv y `python -m pytest` (Entrega 2 y Parte A en verde)

## 2. Corpus

- [x] 2.1 Escribir `entrega_3/corpus/corpus_clinica.json` con 12 a 15 documentos según design D3 (incluida la política de cargos derogada) y `entrega_3/tests/test_corpus.py`: estructura, ids únicos, categorías de la lista cerrada, `vigente` booleano, una política vigente y una derogada con distinto monto, una cobertura por cada obra social del padrón y coherencia con `politica_cargos.json`, `agenda.json` y `estudios.json` (spec `corpus-clinica`). Verificar con `pytest` y **con tu revisión del texto antes del commit**
- [x] 2.2 Agregar al `informe.md` la sección B.1: tabla del corpus (id, categoría, metadatos), por qué cada tema (lo que le faltó al modelo en la Entrega 1) y qué va en metadatos y qué en el texto. Verificar que la tabla coincida con el JSON

## 3. Base de conocimiento

- [x] 3.1 Crear `entrega_3/base_conocimiento.py` (design D2, D4 y D5): embeddings jina con fastembed detrás de la interfaz `Embeddings`, carga del corpus como `Document`, índice Chroma persistido con huella, `buscar(pregunta, k, filtro)` con similitud y `supera_umbral` (umbral provisorio 0.35). Agregar `tests/test_base_conocimiento.py` sobre un índice temporal: reindexa si cambia el corpus y reutiliza si no, k y orden, la política de cargos vigente primero para "¿me cobran si cancelo a último momento?", la derogada excluida con el filtro y presente sin él, y filtro por categoría. Verificar con `pytest` en el venv
- [ ] 3.2 Crear `entrega_3/rag.py` con la consola de búsqueda (design D15): `indexar`, `ver` y `buscar "pregunta" [--todas]`. Verificar corriendo los tres comandos desde la raíz

## 4. Calibración del umbral

- [ ] 4.1 Escribir `entrega_3/datos/preguntas_calibracion.json` (preguntas dentro y fuera del corpus, con lo que se espera de cada una) y commitearlo **antes de medir**. Verificar con un test de estructura
- [ ] 4.2 Agregar `rag.py calibrar` (design D6), correrlo, guardar la tabla en `entrega_3/evidencia/calibracion_<fecha>.txt` y fijar el umbral como constante con un comentario que remita a la evidencia. Agregar a los tests de la base los escenarios de umbral de la spec ("¿atienden a domicilio?" no supera; "¿qué tengo que llevar el día del turno?" sí). Verificar con `pytest`

## 5. Generación con LCEL

- [ ] 5.1 Escribir `entrega_3/prompts/rag_v1.txt` y `sin_grounding_v1.txt` (design D8) y, en `rag.py`, `crear_modelo()` y la cadena LCEL con el fallback antes del LLM (design D7). Agregar `tests/test_rag.py` con un modelo falso: el contexto lleva los ids, sin documentos sobre el umbral el modelo no se llama, y la simulación sin key devuelve el primer documento con su cita. Verificar con `pytest`
- [ ] 5.2 Implementar el guardrail de citas, montos y porcentajes y el `ResultadoRag` (design D9 y D10). Agregar los tests de los escenarios de la spec `respuesta-rag`: cita no recuperada, monto inventado, sin citas, respuesta respaldada, fallback del modelo y error de comunicación. Verificar con `pytest`
- [ ] 5.3 Agregar `rag.py preguntar "pregunta"` y documentar en el README los comandos de `rag.py` (indexar, ver, buscar, preguntar) y que la primera indexación baja el modelo. Agregar al informe la sección B.2 (arquitectura: diagrama de la cadena, modelo, k, filtro híbrido con la demo de la derogada, umbral y guardrail). Verificar que los comandos del README corren tal cual

## 6. Comparación B.3

- [ ] 6.1 Escribir `entrega_3/datos/preguntas_comparacion.json` con las 5 preguntas de design D14, lo esperado con RAG y la respuesta de la Entrega 1 cuando existe, y commitearlo **antes de la corrida real**. Verificar con un test de estructura (al menos 2 preguntas con evidencia de la Entrega 1 y al menos 1 fuera del corpus)
- [ ] 6.2 Agregar `rag.py comparar` (con pausa entre llamadas y modo simulación) y un test en simulación. Verificar con `pytest` y corriendo `python entrega_3/rag.py comparar` sin key
- [ ] 6.3 Correr la comparación contra Groq y guardar la salida en `entrega_3/evidencia/comparacion_groq_<fecha>.txt` (con `org_[OCULTO]` si aparece). Registrar qué preguntas dieron lo esperado y cuáles no, sin modificar las preguntas
- [ ] 6.4 Agregar al informe la sección B.3: tabla antes/después con las respuestas literales de la evidencia y análisis (qué se inventó sin grounding, qué cambió con RAG, la pregunta fuera del corpus). Verificar cada cita contra el archivo de evidencia

## 7. Integración con el workflow

- [ ] 7.1 Escribir `entrega_3/prompts/extraccion_v4.txt` (design D12) y `tests/test_prompt_v4.py`: los mismos chequeos que el v3, el ejemplo de manejar después de dilatar como `otra` y el de síntoma como `consulta_medica`, y v3 sin cambios. Verificar con `pytest`
- [ ] 7.2 Agregar los casos W10, W11 y W12 a `lote_workflow.json` y el `motivo` esperado para `otra` (design D13), y commitearlos **antes de la corrida real**. Verificar con el test de estructura del lote
- [ ] 7.3 En `workflow.py`, usar el prompt v4 y resolver `otra` con el RAG inyectable (design D11): pasos 7, 10 y 11 en la traza, mapeo de estados y motivos, texto anonimizado al RAG y respuesta del RAG al paciente. Agregar tests con un RAG falso para los tres resultados (respondida, sin información, no verificada), uno que confirme que el RAG no recibe el DNI y uno que confirme que un mensaje que no es `otra` no crea el RAG. Verificar con `pytest` (incluidos los 12 casos del lote en simulación) y con `python entrega_3/workflow.py --simulacion`
- [ ] 7.4 Correr el lote completo contra Groq y guardar la salida en `entrega_3/evidencia/workflow_groq_<fecha>.txt`. Registrar cuáles dieron el estado esperado y cuáles no, sin modificar el lote
- [ ] 7.5 Actualizar el informe: la rama de `otra` en el diagrama y la tabla de pasos de la Parte A, una sección de integración con la traza de W10 y W11 tomada literal de la evidencia, y el prompt v4. Actualizar el README (12 casos, tiempo estimado) y el árbol de `entrega_3/`. Verificar que cada número coincida con la evidencia

## 8. Verificación final

- [ ] 8.1 En el venv: `python -m pytest` (Entrega 2 y Entrega 3 en verde), `python entrega_2/app.py` y `python entrega_3/workflow.py --simulacion` sin key, búsqueda de keys en el historial (`gsk_`, `sk-`, `AIza`, `sk-ant-`, `org_`) y `openspec validate entrega-3-parte-b-rag --strict`

## Workflow follow-up

- Revisión del usuario y push.
- Archivar el cambio con `/opsx:archive` para sincronizar las specs vigentes.
