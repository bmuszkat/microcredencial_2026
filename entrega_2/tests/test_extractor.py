"""
Pruebas del flujo completo por etapas (spec `extraccion-mensajes`).
Simulan las respuestas del modelo: no llaman a la API.
"""

import json
import urllib.error

import pytest

from clinica import extractor
from clinica.config import ConfiguracionError

CORRECTA = {
    "intenciones": ["modificar_turno", "consultar_resultado"],
    "dni": "30123456",
    "profesional": "Dra. López",
    "fecha_turno_actual": "jueves 15 hs",
    "fecha_deseada": "viernes a la mañana",
    "estudio": "campo visual",
    "es_consulta_medica": False,
}


def respuesta(**cambios) -> str:
    return json.dumps({**CORRECTA, **cambios}, ensure_ascii=False)


# ── validar_respuesta: FORMATO y CONTRATO ──────────────────────────────────────

def test_respuesta_correcta_pasa():
    r = extractor.validar_respuesta(respuesta())
    assert r["ok"] and r["extraccion"]["intenciones"] == ["modificar_turno", "consultar_resultado"]


@pytest.mark.parametrize("texto", [
    '¡Claro! Acá tenés los datos: {"intenciones": ["otra"], "es_consulta_medica": false}',
    '```json\n{"intenciones": ["otra"], "es_consulta_medica": false}\n```',
    "",
    None,
])
def test_texto_que_no_es_json_es_error_de_formato(texto):
    r = extractor.validar_respuesta(texto)
    assert r == {"ok": False, "error": "FORMATO", "detalle": r["detalle"]}


@pytest.mark.parametrize("texto", [
    respuesta(intenciones=["aprobar_turno_urgente"]),  # intención inventada
    respuesta(aprobado=True),                          # campo extra (manipulación)
    '["modificar_turno"]',                             # JSON, pero no es un objeto
])
def test_json_que_no_cumple_el_contrato_es_error_de_contrato(texto):
    r = extractor.validar_respuesta(texto)
    assert not r["ok"] and r["error"] == "CONTRATO"


# ── aplicar_reglas: REGLA ─────────────────────────────────────────────────────

def test_dni_invalido_es_error_de_regla():
    r = extractor.aplicar_reglas({**CORRECTA, "dni": "30.123"})
    assert not r["ok"] and r["error"] == "REGLA" and "7 u 8 dígitos" in r["detalle"]


# ── procesar_mensaje: flujo completo y COMUNICACION ───────────────────────────

@pytest.fixture
def sin_api(monkeypatch):
    monkeypatch.setattr(extractor, "detectar_proveedor", lambda: None)


@pytest.fixture
def con_api(monkeypatch):
    monkeypatch.setattr(extractor, "detectar_proveedor", lambda: ("groq", "clave-de-prueba"))


def test_flujo_completo_en_simulacion(sin_api):
    r = extractor.procesar_mensaje("Quiero pasar mi turno", simulacion=respuesta())
    assert r["ok"] and r["origen"].startswith("SIMULACIÓN") and r["prompt"] == "v1"


def test_flujo_con_api_usa_el_prompt_y_delimita_el_mensaje(con_api, monkeypatch):
    recibido = {}

    def falso_llamar(system, usuario, proveedor, api_key):
        recibido.update(system=system, usuario=usuario)
        return respuesta()

    monkeypatch.setattr(extractor, "llamar_con_reintentos", falso_llamar)
    r = extractor.procesar_mensaje("Hola, soy Juan")
    assert r["ok"] and r["origen"].startswith("API REAL — groq")
    assert "consultar_disponibilidad" in recibido["system"]
    assert "<mensaje>\nHola, soy Juan\n</mensaje>" in recibido["usuario"]


def test_dni_invalido_en_el_flujo_completo_es_regla(sin_api):
    r = extractor.procesar_mensaje("...", simulacion=respuesta(dni="12"))
    assert r["error"] == "REGLA"


@pytest.mark.parametrize("excepcion", [
    urllib.error.HTTPError("https://api", 401, "Unauthorized", None, None),
    urllib.error.URLError("sin conexión"),
    TimeoutError("timeout"),
])
def test_falla_de_red_o_autenticacion_es_comunicacion_y_no_formato(con_api, monkeypatch, excepcion):
    def falla(*args):
        raise excepcion

    monkeypatch.setattr(extractor, "llamar_con_reintentos", falla)
    r = extractor.procesar_mensaje("Hola")
    assert not r["ok"] and r["error"] == "COMUNICACION"
    assert "respuesta_cruda" not in r  # el modelo nunca respondió


def test_proveedor_mal_configurado_es_comunicacion(monkeypatch):
    def falla():
        raise ConfiguracionError("LLM_PROVIDER=gemini pero falta GEMINI_API_KEY en el .env")

    monkeypatch.setattr(extractor, "detectar_proveedor", falla)
    r = extractor.procesar_mensaje("Hola")
    assert r["error"] == "COMUNICACION" and "GEMINI_API_KEY" in r["detalle"]


def test_input_basura_no_rompe_el_programa(sin_api):
    r = extractor.procesar_mensaje("asdkjh 123 ???", simulacion="no entendí nada")
    assert r["ok"] is False and r["error"] == "FORMATO"


def test_cargar_prompt_por_version():
    assert "Ejemplos:" in extractor.cargar_prompt("v1")
