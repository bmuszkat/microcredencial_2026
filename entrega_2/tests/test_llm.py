"""Pruebas de los reintentos (spec `proveedor-llm`). Simulan la API: no usan red."""

import urllib.error

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
