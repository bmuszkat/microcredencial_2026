# Asistente de turnos y resultados — Clínica Oftalmológica

Microcredencial #2 — Diseño de Aplicaciones Inteligentes (ORT) · Grupo 1

## Caso elegido

Clínica oftalmológica que recibe por WhatsApp y mail pedidos libres de pacientes
(sacar, reprogramar o cancelar turnos y consultar si sus estudios están listos),
que hoy el personal administrativo interpreta y carga a mano. Proponemos un asistente
con IA que interprete esos mensajes y los convierta en operaciones validadas sobre
el sistema de turnos.

## Integrantes

- Brian Muszkat
- Brian Kanelson

## Entregas

| Entrega | Contenido |
|---|---|
| [Entrega 1](entrega_1/informe.md) | Diagnóstico, ficha de oportunidad y concepto de solución |
| [Entrega 2](entrega_2/informe.md) | Primer prototipo operativo: prompt versionado, API real y JSON validado ([resultados del lote](entrega_2/resultados_lote.md) · [evaluación sobre 50 mensajes](entrega_2/evaluacion.md)) |
| [Entrega 3](entrega_3/informe.md) | Workflow encadenado con puntos de control (Parte A, Hito 1: 9/9 casos contra Groq). RAG y agente: en curso |

## Cómo correrlo (Entrega 2)

Requisitos: **Python 3.10 a 3.13** (el grupo usa 3.12, declarado en `.python-version`). La Parte B de la Entrega 3 usa ChromaDB y fastembed, que dependen de `onnxruntime`, y `onnxruntime` no instala en versiones más nuevas de Python. Todos los comandos se corren **desde la raíz del repo**.

Conviene trabajar en un entorno virtual. Con [uv](https://docs.astral.sh/uv/) (baja Python 3.12 si no está instalado):

```bash
uv venv --python 3.12 .venv
.venv\Scripts\activate        # en Linux o macOS: source .venv/bin/activate
uv pip install -r requirements.txt
```

O, si ya hay un Python 3.10 a 3.13 instalado, sin uv:

```bash
py -3.12 -m venv .venv        # en Linux o macOS: python3.12 -m venv .venv
.venv\Scripts\activate        # en Linux o macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Después, con el entorno activado:

```bash
cp .env.example .env          # completar la API key del proveedor (ver abajo)
                              # (en el cmd de Windows: copy .env.example .env)

python entrega_2/app.py          # corre el lote de 4 casos con el prompt vigente (v2)
python entrega_2/app.py v1       # lo mismo con otra versión del prompt (v1, zeroshot)
python entrega_2/evaluar.py      # evalúa el set de 50 mensajes con el prompt vigente (~18 min con Groq gratis)
python entrega_2/evaluar.py v1   # lo mismo con otra versión, para comparar
python -m pytest entrega_2       # pruebas automáticas (no usan la API)
```

**Proveedor de LLM:** alcanza con completar en el `.env` **una** key de Groq, OpenAI, Anthropic o Gemini: se usa el primer proveedor que tenga key (en ese orden). Para forzar uno en particular, definir `LLM_PROVIDER`. El grupo usa **Groq** con el modelo `openai/gpt-oss-20b` (key gratuita en https://console.groq.com). Sin ninguna key, `app.py` y `evaluar.py` corren en **modo simulación** con respuestas de ejemplo.

**Evaluación larga:** `evaluar.py` espera 20 s entre llamadas para no superar el límite gratuito de Groq y guarda cada resultado apenas llega en `entrega_2/evidencia/evaluacion_<versión>.json`. Si se corta, al volver a correrlo sigue desde donde quedó (`--desde-cero` para empezar de nuevo, `--limite 3` para una prueba rápida).

> La API key nunca se escribe en el código: vive solo en el `.env`, que está en el `.gitignore`.

## Cómo correrlo (Entrega 3)

Mismos requisitos y mismo `.env` que la Entrega 2. Desde la raíz del repo:

```bash
python entrega_3/workflow.py                   # workflow sobre el lote de 9 casos (~7 min con Groq gratis)
python entrega_3/workflow.py --simulacion      # el lote con respuestas simuladas, sin llamar a la API
python entrega_3/workflow.py "mensaje libre"   # un mensaje suelto contra el LLM real
python -m pytest entrega_3                     # pruebas automáticas (no usan la API)
```

**Workflow:** cada caso muestra la traza paso a paso (📏 regla, 🤖 LLM, 🔎 sensor), el estado de cada intención, el estado global y la respuesta al paciente, y al final cuántos casos dieron el estado esperado. Con Groq espera 20 s entre llamadas (`--pausa N` para cambiarlo). Sin ninguna key corre en modo simulación. Los datos de la clínica (padrón, agenda, estudios y política de cargos) son ficticios y están en `entrega_3/datos/`.

## Estructura del repo

```
├── README.md
├── requirements.txt          ← dependencias (pip install -r requirements.txt)
├── .python-version           ← versión de Python del grupo (3.12)
├── .env.example              ← variables de entorno SIN valores (el .env real no se sube)
├── entrega_1/
│   ├── informe.md            ← Partes A y B de la Entrega 1
│   ├── main.py               ← práctica de la Clase 1 (prompt ingenuo contra LLM real)
│   └── evidencia/            ← respuestas reales de los modelos (A.2)
├── entrega_2/
│   ├── app.py                ← punto de entrada: corre el lote y muestra la tabla
│   ├── evaluar.py            ← evalúa el set de 50 mensajes y calcula las métricas
│   ├── informe.md            ← técnica de prompting, prompt v2, contrato, privacidad y reflexión
│   ├── resultados_lote.md    ← tabla del lote de prueba (corridas reales v2 y v1)
│   ├── evaluacion.md         ← evaluación sobre 50 mensajes: v1 vs v2 e hipótesis B.5
│   ├── clinica/              ← el componente, un módulo por responsabilidad
│   │   ├── config.py         ← lee el .env y elige el proveedor de LLM
│   │   ├── llm.py            ← llamada HTTP a Groq / OpenAI / Anthropic / Gemini, con reintentos
│   │   ├── contrato.py       ← contratos de datos (Pydantic) por versión de prompt
│   │   ├── reglas.py         ← reglas de negocio en código (formato del DNI)
│   │   └── extractor.py      ← el flujo: mensaje → LLM → json.loads → contrato → reglas
│   ├── prompts/
│   │   ├── extraccion_v2.txt       ← system prompt vigente (few-shot)
│   │   ├── extraccion_v1.txt       ← versión anterior, se conserva para comparar
│   │   └── extraccion_zeroshot.txt ← el v1 sin ejemplos, para comparar técnicas
│   ├── datos/
│   │   ├── lote_prueba.json  ← los 4 casos: típico, ambiguo, manipulación, caso límite
│   │   └── set_evaluacion.json ← 50 mensajes con su respuesta esperada
│   ├── evidencia/            ← salidas de las corridas reales contra Groq
│   └── tests/                ← pruebas automáticas sin API
├── entrega_3/
│   ├── informe.md            ← A.2 (diagrama del workflow) y A.3 (prueba de falla controlada)
│   ├── workflow.py           ← Parte A: los 12 pasos, la traza y el punto de entrada por consola
│   ├── reglas.py             ← reglas en código: anonimizar el DNI, fechas relativas, cargo, estado global
│   ├── herramientas.py       ← sensores de solo lectura sobre los datos de la clínica
│   ├── redactor.py           ← respuesta al paciente: plantillas, redacción con datos validados y guardrail
│   ├── prompts/
│   │   ├── extraccion_v3.txt ← el v2 con el DNI anonimizado y los fallos s12 y p02 corregidos
│   │   └── redaccion_v1.txt  ← redacción con formato fijo (dd/mm, HH:MM, $12.000)
│   ├── datos/                ← padrón, agenda, estudios y política de cargos (ficticios) y el lote de 9 casos
│   ├── evidencia/            ← salida de la corrida real contra Groq
│   └── tests/                ← pruebas automáticas sin API (clinica/ se importa desde entrega_2)
└── openspec/                 ← specs y cambios (desarrollo guiado por especificaciones)
```
