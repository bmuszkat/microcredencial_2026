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
| [Entrega 2](entrega_2/informe.md) | Primer prototipo operativo: prompt versionado, API real y JSON validado ([resultados del lote](entrega_2/resultados_lote.md)) |

## Cómo correrlo (Entrega 2)

Requisitos: Python 3.10 o superior. Todos los comandos se corren **desde la raíz del repo**.

```bash
pip install -r requirements.txt
cp .env.example .env          # completar la API key del proveedor (ver abajo)

python entrega_2/app.py       # corre el lote de prueba con el prompt v1
python entrega_2/app.py v2    # lo mismo con otra versión (si existe entrega_2/prompts/extraccion_v2.txt)
python -m pytest entrega_2    # pruebas del contrato, las reglas y el flujo (no usan la API)
```

**Proveedor de LLM:** se elige en el `.env` con `LLM_PROVIDER` (`groq`, `openai`, `anthropic` o `gemini`) y la key correspondiente. El grupo usa **Groq** con el modelo `openai/gpt-oss-20b` (key gratuita en https://console.groq.com). Si `LLM_PROVIDER` no está definido, se usa el primer proveedor con key; sin ninguna key, `app.py` corre en **modo simulación** con respuestas de ejemplo.

> La API key nunca se escribe en el código: vive solo en el `.env`, que está en el `.gitignore`.

## Estructura del repo

```
├── README.md
├── requirements.txt          ← dependencias (pip install -r requirements.txt)
├── .env.example              ← variables de entorno SIN valores (el .env real no se sube)
├── entrega_1/
│   ├── informe.md            ← Partes A y B de la Entrega 1
│   ├── main.py               ← práctica de la Clase 1 (prompt ingenuo contra LLM real)
│   └── evidencia/            ← respuestas reales de los modelos (A.2)
├── entrega_2/
│   ├── app.py                ← punto de entrada: corre el lote y muestra la tabla
│   ├── informe.md            ← técnica de prompting, prompt v1, contrato y reflexión
│   ├── resultados_lote.md    ← tabla del lote de prueba (corrida real)
│   ├── clinica/              ← el componente, un módulo por responsabilidad
│   │   ├── config.py         ← lee el .env y elige el proveedor de LLM
│   │   ├── llm.py            ← llamada HTTP a Groq / OpenAI / Anthropic / Gemini, con reintentos
│   │   ├── contrato.py       ← contrato de datos (Pydantic): qué debe devolver el LLM
│   │   ├── reglas.py         ← reglas de negocio en código (formato del DNI)
│   │   └── extractor.py      ← el flujo: mensaje → LLM → json.loads → contrato → reglas
│   ├── prompts/
│   │   └── extraccion_v1.txt ← system prompt versionado (few-shot)
│   ├── datos/
│   │   └── lote_prueba.json  ← los 4 casos: típico, ambiguo, manipulación, caso límite
│   └── tests/                ← pruebas automáticas sin API
└── openspec/                 ← specs y cambios (desarrollo guiado por especificaciones)
```
