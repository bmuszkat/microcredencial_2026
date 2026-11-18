"""
Llamada a la API real del modelo (request → response), por HTTP directo con urllib.

Soporta cuatro proveedores (spec `proveedor-llm`):
    groq, openai → formato chat-completions (compatible con OpenAI)
    anthropic    → /v1/messages
    gemini       → generateContent

A todos se les pide temperatura 0 y salida JSON. El proveedor y el modelo se eligen
en el .env: el resto del componente no depende de cuál se use.
"""

import json
import re
import time
import urllib.error
import urllib.request
from typing import Optional

from .config import MODELOS_POR_DEFECTO, SSL_CONTEXT, modelo_de

TIMEOUT_SEGUNDOS = 60
REINTENTOS = 3
CODIGOS_REINTENTABLES = (429, 503)  # 429: límite de uso · 503: servidor saturado
ESPERA_MAXIMA_SEGUNDOS = 30


class RespuestaNoJSON(Exception):
    """
    El modelo SÍ respondió, pero no generó JSON válido y el proveedor rechazó la salida
    (Groq/OpenAI en modo JSON devuelven HTTP 400 con code "json_validate_failed").
    Es un error de FORMATO, no de comunicación. `generacion` es lo que el modelo produjo.
    """

    def __init__(self, mensaje: str, generacion: str):
        super().__init__(mensaje)
        self.generacion = generacion


def cuerpo_del_error(e: urllib.error.HTTPError) -> str:
    """Lee (una sola vez) el cuerpo de la respuesta de error de la API y lo guarda en el error."""
    if not hasattr(e, "cuerpo"):
        try:
            e.cuerpo = e.read().decode("utf-8", errors="replace") if e.fp else ""
        except Exception:
            e.cuerpo = ""
    return e.cuerpo


def mensaje_del_error(e: urllib.error.HTTPError) -> str:
    """'HTTP 401: Invalid API Key' en lugar de un genérico 'Bad Request'."""
    try:
        detalle = json.loads(cuerpo_del_error(e))["error"]["message"]
    except (ValueError, KeyError, TypeError):
        detalle = cuerpo_del_error(e)[:300] or e.reason
    return f"HTTP {e.code}: {detalle}"


def _espera_sugerida(e: urllib.error.HTTPError) -> Optional[float]:
    """Segundos que pide esperar la API: header Retry-After o 'try again in 2.55s' en el mensaje."""
    if e.headers is not None and e.headers.get("retry-after"):
        try:
            return float(e.headers.get("retry-after"))
        except ValueError:
            pass
    encontrado = re.search(r"try again in ([\d.]+)s", cuerpo_del_error(e))
    return float(encontrado.group(1)) if encontrado else None


def _json_rechazado(e: urllib.error.HTTPError) -> Optional[RespuestaNoJSON]:
    """Si el 400 es porque el modelo no generó JSON válido, lo convierte en RespuestaNoJSON."""
    if e.code != 400:
        return None
    try:
        error = json.loads(cuerpo_del_error(e))["error"]
    except (ValueError, KeyError, TypeError):
        return None
    if error.get("code") != "json_validate_failed":
        return None
    return RespuestaNoJSON(error.get("message", "JSON inválido"), error.get("failed_generation") or "")


def _post_json(url: str, payload: dict, headers: dict) -> dict:
    """Request HTTP POST: manda un JSON y devuelve el JSON de la respuesta."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "clinica-entrega2/1.0", **headers},
    )
    with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=TIMEOUT_SEGUNDOS) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _llamar_chat_completions(system: str, usuario: str, api_key: str, url: str, modelo: str) -> str:
    """Formato compatible con OpenAI: sirve para OpenAI y para Groq."""
    payload = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": usuario},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    data = _post_json(url, payload, {"Authorization": f"Bearer {api_key}"})
    return data["choices"][0]["message"]["content"]


def _llamar_anthropic(system: str, usuario: str, api_key: str, modelo: str) -> str:
    """Anthropic no tiene modo JSON nativo: el formato lo impone el prompt."""
    payload = {
        "model": modelo,
        "max_tokens": 1024,
        "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": usuario}],
    }
    data = _post_json(
        "https://api.anthropic.com/v1/messages",
        payload,
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    return "".join(bloque.get("text", "") for bloque in data["content"] if bloque.get("type") == "text")


def _llamar_gemini(system: str, usuario: str, api_key: str, modelo: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": usuario}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    data = _post_json(url, payload, {"x-goog-api-key": api_key})
    return data["candidates"][0]["content"]["parts"][0]["text"]


def llamar_modelo(system: str, usuario: str, proveedor: str, api_key: str) -> str:
    """Una sola llamada. Devuelve el TEXTO crudo del modelo (todavía no es un dict)."""
    if proveedor not in MODELOS_POR_DEFECTO:
        raise ValueError(f"Proveedor desconocido: {proveedor}")
    modelo = modelo_de(proveedor)
    if proveedor == "groq":
        return _llamar_chat_completions(
            system, usuario, api_key, "https://api.groq.com/openai/v1/chat/completions", modelo
        )
    if proveedor == "openai":
        return _llamar_chat_completions(
            system, usuario, api_key, "https://api.openai.com/v1/chat/completions", modelo
        )
    if proveedor == "anthropic":
        return _llamar_anthropic(system, usuario, api_key, modelo)
    if proveedor == "gemini":
        return _llamar_gemini(system, usuario, api_key, modelo)
    raise ValueError(f"Proveedor desconocido: {proveedor}")


def llamar_con_reintentos(system: str, usuario: str, proveedor: str, api_key: str) -> str:
    """
    Un error transitorio (429, 503) se reintenta. La espera es la que pide la API
    (Retry-After o "try again in Xs"), o como mínimo 2 s y 4 s; nunca más de 30 s.
    Una key inválida (401/403) o un pedido mal armado (400) NO se reintenta: fallaría igual.
    Si el 400 es porque el modelo no generó JSON válido, se lanza RespuestaNoJSON (FORMATO).
    """
    for intento in range(1, REINTENTOS + 1):
        try:
            return llamar_modelo(system, usuario, proveedor, api_key)
        except urllib.error.HTTPError as e:
            rechazo = _json_rechazado(e)
            if rechazo is not None:
                raise rechazo from e
            if e.code in CODIGOS_REINTENTABLES and intento < REINTENTOS:
                espera = min(max(_espera_sugerida(e) or 0, 2 ** intento), ESPERA_MAXIMA_SEGUNDOS)
                print(f"  ⏳ HTTP {e.code} (intento {intento}/{REINTENTOS}). Reintento en {espera:.1f} s...")
                time.sleep(espera)
                continue
            raise
    raise RuntimeError("No debería llegar acá")
