# Proposal

## Why

En la Entrega 1 (A.2), sin datos de la clínica, Gemini inventó una política ("según el Punto 4.2… un cargo administrativo de $5.000") y una cobertura ("OSDE 210 cubre el campo visual al 100 %"), y lo dijo con total seguridad. La Parte A resolvió eso para los datos estructurados (agenda, estudios y cargos), pero las preguntas informativas (políticas, coberturas, preparación de estudios, sedes, documentación) siguen terminando en `otra` con una respuesta fija que no ayuda al paciente. La Parte B de la Entrega 3 pide un **RAG** (Clase 5): un corpus del caso, búsqueda semántica con filtrado híbrido y un LLM que responda **solo** con lo recuperado, o diga que no tiene la información.

## What Changes

- **Corpus de la clínica** en `entrega_3/corpus/corpus_clinica.json`: entre 12 y 15 documentos ficticios pero coherentes con los datos de la Parte A. Cada uno tiene una `descripcion_semantica` rica (sinónimos, formas en que lo pregunta un paciente) y metadatos filtrables (`categoria`, `vigente`, `version` y, cuando aplica, `sede` y `obra_social`). Incluye a propósito **una versión derogada de la política de cargos**. *(Consigna B.1: 10 a 15 documentos del caso, `descripcion_semantica` y al menos 2 metadatos; lo exacto en metadatos, lo descriptivo en el texto.)*
- **Base de conocimiento** en `entrega_3/base_conocimiento.py`: embeddings locales en español (`jinaai/jina-embeddings-v2-base-es` con fastembed, sin key), índice ChromaDB persistido en disco y reconstruido solo si cambia el corpus, recuperación de los k=3 documentos más similares y **filtrado híbrido** (semántico + `where={"vigente": True}`). *(B.2: índice con ChromaDB, top-k, filtrado híbrido.)*
- **Umbral de similitud calibrado** con preguntas dentro y fuera del corpus, con la medición guardada como evidencia. Si ningún documento lo supera, la respuesta es el fallback **sin llamar al LLM**. *(B.2: "Si no se puede deducir: 'No tengo información oficial sobre esa consulta.'")*
- **Generación con una cadena LCEL** en `entrega_3/rag.py`, con el system prompt de la consigna en `entrega_3/prompts/rag_v1.txt` y el proveedor del `.env` (Groq, `openai/gpt-oss-20b`). Un **guardrail en código** verifica que los documentos citados estén entre los recuperados y que cada monto y porcentaje del texto aparezca en ellos. *(B.2; mismo principio que el paso 11 de la Parte A.)*
- **Comparación antes/después** (`python entrega_3/rag.py comparar`): las mismas preguntas sin grounding y con RAG, entre ellas las dos que Gemini respondió inventando en la Entrega 1 y una fuera del corpus que tiene que dar el fallback. Las preguntas y lo que se espera de cada una se commitean **antes** de correr. *(B.3; la pregunta fuera del corpus apunta a "Destacado".)*
- **Integración con el workflow de la Parte A**: un mensaje con intención `otra` pasa por el RAG en lugar de la plantilla fija. **Prompt de extracción v4**: separa una indicación publicada de la clínica (preparación de un estudio, qué llevar) de una duda clínica o un síntoma, que sigue siendo `consulta_medica` y se deriva.
- **Entorno instalable**: las dependencias nuevas van en `requirements.txt`, el modelo de embeddings queda declarado en el código y el README explica cómo crear el entorno con Python 3.12, indexar (la primera vez baja el modelo) y correr.

### Fuera de alcance

- **Mensajes que mezclan un pedido administrativo con una pregunta informativa** ("quiero turno y ¿qué tengo que llevar?"). El contrato no permite combinar `otra` con otra intención, así que la pregunta informativa no se responde en ese mensaje → **Entrega 4** (nueva intención o contrato v3).
- **Responder dudas clínicas con el RAG.** Aunque el corpus tenga indicaciones de preparación, un síntoma o un pedido de opinión médica sigue yendo a una persona (Matriz B.4 de la Entrega 1).
- **Dividir documentos largos en fragmentos (chunking) y búsqueda léxica (BM25).** Los documentos son cortos y cada uno trata un tema; el "híbrido" de esta entrega es semántico + metadatos, como pide la consigna → **Entrega 4** si el corpus crece.
- **Evaluación cuantitativa del RAG sobre un set grande** (precisión de recuperación, fidelidad) → **Entrega 4** (matriz de pruebas).
- **Agente con LangGraph** que use el RAG como herramienta → **Parte C**.
- **Reevaluar el prompt v4 sobre los 50 mensajes de la Entrega 2** → **Entrega 4**, igual que el v3.

## Capabilities

### New Capabilities

- `corpus-clinica`: los documentos informativos de la clínica, su estructura (texto semántico y metadatos) y su coherencia con los datos del backend. *(B.1)*
- `base-conocimiento`: indexar el corpus con embeddings, persistir el índice y recuperar los documentos más similares con filtro por metadatos y umbral de similitud. *(B.2)*
- `respuesta-rag`: responder una pregunta informativa solo con los documentos recuperados (cadena LCEL), el fallback cuando no hay información, el guardrail de citas y montos, y la comparación con y sin grounding. *(B.2, B.3)*

### Modified Capabilities

- `workflow-pedidos`: la intención `otra` deja de responderse con una plantilla fija y pasa por el RAG, con un `motivo` que distingue si se respondió, si no había información oficial o si falló.
- `respuesta-paciente`: la respuesta de `otra` deja de ser una plantilla fija y pasa a ser la del RAG (o su fallback).
- `extraccion-mensajes`: el workflow usa el prompt `v4`, que separa las indicaciones publicadas (`otra`) de las dudas clínicas (`consulta_medica`).

## Impact

- **Código nuevo en `entrega_3/`:** `corpus/`, `base_conocimiento.py`, `rag.py`, `prompts/rag_v1.txt`, `prompts/sin_grounding_v1.txt`, `prompts/extraccion_v4.txt`, datos de la comparación, evidencia y tests. Se modifican `workflow.py` (la rama de `otra` y la versión del prompt), `datos/lote_workflow.json` (casos nuevos) e `informe.md` (Parte B).
- **`entrega_2/` no se modifica.**
- **Dependencias nuevas** en `requirements.txt`: `langchain-core`, `langchain-openai`, `langchain-chroma` (trae ChromaDB) y `fastembed`. ChromaDB no tiene versión para Python 3.14 o superior, así que el proyecto pasa a requerir **Python 3.10 a 3.13** (el grupo usa 3.12, en un `.venv` creado con `uv`).
- **Modelo de embeddings:** `jinaai/jina-embeddings-v2-base-es` se baja de Hugging Face la primera vez que se indexa (unos 640 MB) y queda en caché. No usa key.
- **Archivos generados:** el índice (`entrega_3/indice_chroma/`) va en el `.gitignore`; se regenera con `python entrega_3/rag.py indexar`.
- **Costo de API:** la comparación hace 2 llamadas por pregunta (sin grounding y con RAG) y 1 cuando la pregunta cae en el fallback; con 4 a 5 preguntas y 20 s de pausa son unos 3 minutos. El lote del workflow suma los casos nuevos.
