"""
El componente completo: pasos 2 y 3 del user journey de la Entrega 1.

    Mensaje → [LLM + prompt] → texto → json.loads() → contrato → regla DNI → extracción validada
     paso 2                            └──────── paso 3 (validación) ────────┘

Cada etapa puede fallar, y cada falla se informa por separado (spec `extraccion-mensajes`):
    COMUNICACION → el modelo no respondió (red, key, saturación, configuración)
    FORMATO      → respondió algo que no es JSON
    CONTRATO     → es JSON pero no cumple el contrato (claves, tipos, intenciones)
    REGLA        → cumple el contrato pero un dato no es válido para el negocio (DNI)
"""

import json
import urllib.error
from typing import Optional

from pydantic import ValidationError

from .config import RAIZ_ENTREGA, ConfiguracionError, detectar_proveedor, modelo_de
from .contrato import ExtraccionPacienteV1 as ExtraccionPaciente  # tarea 1.2: contrato según versión
from .llm import RespuestaNoJSON, llamar_con_reintentos, mensaje_del_error
from .reglas import validar_dni

PROMPT_VERSION = "v1"

# Errores que significan "el modelo no llegó a responder". OSError incluye URLError,
# HTTPError y timeouts de red; KeyError/IndexError/ValueError cubren una respuesta HTTP
# con forma inesperada (no es el texto del modelo, es el sobre de la API).
ERRORES_DE_COMUNICACION = (
    urllib.error.URLError, OSError, KeyError, IndexError, ValueError, ConfiguracionError,
)


def cargar_prompt(version: str = PROMPT_VERSION) -> str:
    """El prompt vive en un archivo aparte: así se puede comparar v1 con v2 sin tocar el código."""
    return (RAIZ_ENTREGA / "prompts" / f"extraccion_{version}.txt").read_text(encoding="utf-8")


def armar_mensaje_usuario(mensaje: str) -> str:
    """Delimita el mensaje del paciente para que el modelo lo trate como dato, no como instrucción."""
    return f"Mensaje del paciente (entre <mensaje> y </mensaje>):\n<mensaje>\n{mensaje.strip()}\n</mensaje>"


def validar_respuesta(texto: Optional[str]) -> dict:
    """
    Validación en dos niveles: ¿es JSON? (FORMATO) y ¿cumple el contrato? (CONTRATO).
    No se limpian bloques ```json ni texto alrededor: si el modelo los agrega, rompió
    la regla del prompt y queremos verlo como error de FORMATO (design D6).
    """
    try:
        datos = json.loads(texto or "")
    except json.JSONDecodeError as e:
        return {"ok": False, "error": "FORMATO", "detalle": f"No es JSON válido ({e.msg})"}

    if not isinstance(datos, dict):
        return {"ok": False, "error": "CONTRATO", "detalle": "El JSON no es un objeto {...}"}

    try:
        extraccion = ExtraccionPaciente(**datos)
    except ValidationError as e:
        errores = [f"{'.'.join(map(str, err['loc'])) or 'objeto'}: {err['msg']}" for err in e.errors()]
        return {"ok": False, "error": "CONTRATO", "detalle": errores}

    return {"ok": True, "extraccion": extraccion.model_dump()}


def aplicar_reglas(extraccion: dict) -> dict:
    """Reglas de negocio deterministas sobre una extracción que ya cumple el contrato."""
    valido, motivo = validar_dni(extraccion.get("dni"))
    if not valido:
        return {"ok": False, "error": "REGLA", "detalle": motivo}
    return {"ok": True, "regla_dni": motivo}


def procesar_mensaje(mensaje: str, simulacion: Optional[str] = None, version: str = PROMPT_VERSION) -> dict:
    """
    Flujo completo del componente. Nunca rompe el programa: siempre devuelve un dict
    con "ok" y, si falló, en qué etapa ("error") y por qué ("detalle").
    Si no hay ninguna API key, usa `simulacion` como si fuera la respuesta del modelo.
    """
    try:
        proveedor = detectar_proveedor()
    except ConfiguracionError as e:
        return {"origen": "CONFIGURACIÓN", "prompt": version, "ok": False,
                "error": "COMUNICACION", "detalle": str(e)}

    if proveedor is None:
        origen, texto = "SIMULACIÓN (sin API key en .env)", simulacion
    else:
        nombre, key = proveedor
        origen = f"API REAL — {nombre} ({modelo_de(nombre)})"
        try:
            texto = llamar_con_reintentos(cargar_prompt(version), armar_mensaje_usuario(mensaje), nombre, key)
        except RespuestaNoJSON as e:
            # El modelo respondió, pero no con JSON válido: el proveedor rechazó la salida.
            return {"origen": origen, "prompt": version, "respuesta_cruda": e.generacion, "ok": False,
                    "error": "FORMATO", "detalle": f"El proveedor rechazó la salida por no ser JSON válido ({e})"}
        except urllib.error.HTTPError as e:
            return {"origen": origen, "prompt": version, "ok": False,
                    "error": "COMUNICACION", "detalle": mensaje_del_error(e)}
        except ERRORES_DE_COMUNICACION as e:
            return {"origen": origen, "prompt": version, "ok": False,
                    "error": "COMUNICACION", "detalle": f"{type(e).__name__}: {e}"}

    resultado = {"origen": origen, "prompt": version, "respuesta_cruda": texto, **validar_respuesta(texto)}
    if not resultado["ok"]:
        return resultado
    return {**resultado, **aplicar_reglas(resultado["extraccion"])}
