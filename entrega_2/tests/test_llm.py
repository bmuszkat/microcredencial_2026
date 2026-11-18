"""Pruebas de los reintentos (spec `proveedor-llm`). Simulan la API: no usan red."""

import io
import json
import urllib.error
from email.message import Message

import pytest

from clinica import llm


def error_http(codigo: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.ejemplo", codigo, f"HTTP {codigo}", None, None)


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda segundos: None)


def simular_respuestas(monkeypatch, respuestas):
    """Cada llamada a llamar_modelo devuelve (o lanza) el próximo elemento de la lista."""
    llamadas = []

    def falso_llamar_modelo(system, usuario, proveedor, api_key):
        llamadas.append(proveedor)
        respuesta = respuestas[len(llamadas) - 1]
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(llm, "llamar_modelo", falso_llamar_modelo)
    return llamadas


def test_429_se_reintenta_y_devuelve_la_segunda_respuesta(monkeypatch):
    llamadas = simular_respuestas(monkeypatch, [error_http(429), '{"ok": true}'])
    assert llm.llamar_con_reintentos("sys", "user", "groq", "k") == '{"ok": true}'
    assert len(llamadas) == 2


def test_503_agota_los_reintentos_y_propaga_el_error(monkeypatch):
    llamadas = simular_respuestas(monkeypatch, [error_http(503)] * 3)
    with pytest.raises(urllib.error.HTTPError):
        llm.llamar_con_reintentos("sys", "user", "groq", "k")
    assert len(llamadas) == 3


@pytest.mark.parametrize("codigo", [400, 401, 403])
def test_errores_de_pedido_o_autenticacion_no_se_reintentan(monkeypatch, codigo):
    llamadas = simular_respuestas(monkeypatch, [error_http(codigo), '{"ok": true}'])
    with pytest.raises(urllib.error.HTTPError):
        llm.llamar_con_reintentos("sys", "user", "groq", "k")
    assert len(llamadas) == 1


def test_proveedor_desconocido_es_error():
    with pytest.raises(ValueError, match="desconocido"):
        llm.llamar_modelo("sys", "user", "chatgpt", "k")


# ── Errores reales observados con Groq ─────────────────────────────────────────

def error_con_cuerpo(codigo: int, cuerpo: dict, retry_after: str = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry_after is not None:
        headers["retry-after"] = retry_after
    return urllib.error.HTTPError("https://api", codigo, "x", headers, io.BytesIO(json.dumps(cuerpo).encode()))


def test_429_espera_lo_que_pide_la_api(monkeypatch):
    esperas = []
    monkeypatch.setattr(llm.time, "sleep", esperas.append)
    simular_respuestas(monkeypatch, [error_con_cuerpo(429, {"error": {"message": "x"}}, retry_after="9.5"), "{}"])
    llm.llamar_con_reintentos("sys", "user", "groq", "k")
    assert esperas == [9.5]


def test_429_lee_el_tiempo_del_mensaje_si_no_hay_header(monkeypatch):
    esperas = []
    monkeypatch.setattr(llm.time, "sleep", esperas.append)
    cuerpo = {"error": {"message": "Rate limit reached ... Please try again in 13.62s."}}
    simular_respuestas(monkeypatch, [error_con_cuerpo(429, cuerpo), "{}"])
    llm.llamar_con_reintentos("sys", "user", "groq", "k")
    assert esperas == [13.62]


def test_la_espera_tiene_un_minimo_y_un_maximo(monkeypatch):
    esperas = []
    monkeypatch.setattr(llm.time, "sleep", esperas.append)
    simular_respuestas(monkeypatch, [error_con_cuerpo(429, {}, retry_after="0.1"),
                                     error_con_cuerpo(429, {}, retry_after="999"), "{}"])
    llm.llamar_con_reintentos("sys", "user", "groq", "k")
    assert esperas == [2, llm.ESPERA_MAXIMA_SEGUNDOS]


def test_json_rechazado_por_el_proveedor_es_respuesta_no_json(monkeypatch):
    cuerpo = {"error": {"message": "Failed to validate JSON.", "code": "json_validate_failed",
                        "failed_generation": "Lo siento, no puedo ayudar con eso."}}
    llamadas = simular_respuestas(monkeypatch, [error_con_cuerpo(400, cuerpo)])
    with pytest.raises(llm.RespuestaNoJSON) as error:
        llm.llamar_con_reintentos("sys", "user", "groq", "k")
    assert error.value.generacion == "Lo siento, no puedo ayudar con eso."
    assert len(llamadas) == 1


def test_otro_400_sigue_siendo_http_error():
    e = error_con_cuerpo(400, {"error": {"message": "model not found", "code": "model_not_found"}})
    assert llm._json_rechazado(e) is None
    assert llm.mensaje_del_error(e) == "HTTP 400: model not found"
