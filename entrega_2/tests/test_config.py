"""Pruebas de la selección de proveedor (spec `proveedor-llm`). No llaman a ninguna API."""

import pytest

from clinica import config

VARIABLES = ["LLM_PROVIDER", *config.PROVEEDORES.values(), *(f"{p.upper()}_MODEL" for p in config.PROVEEDORES)]


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch):
    """Cada prueba arranca sin keys ni LLM_PROVIDER (ignora el .env real del desarrollador)."""
    for variable in VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def test_placeholder_del_env_example_no_cuenta_como_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "tu_api_key_de_groq_aqui")
    assert config.key_valida("GROQ_API_KEY") is None


def test_key_vacia_no_cuenta(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "   ")
    assert config.key_valida("GROQ_API_KEY") is None


def test_sin_ninguna_key_es_modo_simulacion():
    assert config.detectar_proveedor() is None


def test_seleccion_automatica_usa_el_unico_configurado(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "clave-de-prueba")
    assert config.detectar_proveedor() == ("openai", "clave-de-prueba")


def test_seleccion_automatica_respeta_el_orden(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave-gemini")
    monkeypatch.setenv("GROQ_API_KEY", "clave-groq")
    assert config.detectar_proveedor() == ("groq", "clave-groq")


def test_proveedor_explicito_gana_sobre_el_orden(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "clave-groq")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-anthropic")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert config.detectar_proveedor() == ("anthropic", "clave-anthropic")


def test_proveedor_explicito_sin_key_es_error_y_no_cae_en_otro(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "clave-groq")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with pytest.raises(config.ConfiguracionError, match="GEMINI_API_KEY"):
        config.detectar_proveedor()


def test_proveedor_desconocido_es_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "chatgpt")
    with pytest.raises(config.ConfiguracionError, match="no es válido"):
        config.detectar_proveedor()


def test_modelo_por_defecto_de_groq():
    assert config.modelo_de("groq") == "openai/gpt-oss-20b"


def test_modelo_configurable_por_env(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    assert config.modelo_de("groq") == "llama-3.3-70b-versatile"
