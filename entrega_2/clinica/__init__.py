"""
Componente de extracción del asistente de la Clínica Oftalmológica (Entrega 2).

Convierte el mensaje libre de un paciente en una extracción estructurada y validada:

    mensaje → [LLM + prompt versionado] → json.loads() → contrato (Pydantic) → reglas → extracción

Módulos:
    config     → lee el .env y elige el proveedor de LLM
    llm        → llamada HTTP al modelo (Groq, OpenAI, Anthropic, Gemini) con reintentos
    contrato   → qué debe devolver el LLM (Pydantic)
    reglas     → reglas de negocio en código (DNI)
    extractor  → el flujo completo, con errores por etapa
"""
