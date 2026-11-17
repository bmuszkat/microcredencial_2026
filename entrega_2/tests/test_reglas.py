"""Pruebas de la regla de DNI (spec `extraccion-mensajes`)."""

import pytest

from clinica.reglas import validar_dni


@pytest.mark.parametrize("dni", ["30123456", "7123456"])
def test_dni_de_7_u_8_digitos_es_valido(dni):
    assert validar_dni(dni)[0] is True


@pytest.mark.parametrize("dni", ["30.123", "30.123.456", "123456", "123456789", "30123A56", ""])
def test_dni_con_formato_invalido_es_rechazado(dni):
    valido, motivo = validar_dni(dni)
    assert valido is False
    assert "7 u 8 dígitos" in motivo


def test_dni_ausente_no_es_error():
    assert validar_dni(None)[0] is True
