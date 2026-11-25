"""
Reglas del dominio de la Entrega 3 (reglas.py).

Se llama test_reglas_dominio.py y no test_reglas.py porque la Entrega 2 ya tiene un
tests/test_reglas.py y pytest no admite dos módulos de test con el mismo nombre.
"""

import pytest

from reglas import MARCADOR_DNI, anonimizar_dni

# ── Paso 0 · Anonimizar el DNI ────────────────────────────────────────────────


@pytest.mark.parametrize("escrito", ["30.123.456", "30123456"])
def test_dni_con_y_sin_puntos(escrito):
    r = anonimizar_dni(f"Hola, soy Juan Pérez, DNI {escrito}. Quiero cambiar mi turno.")
    assert r.dni == "30123456"
    assert r.texto == f"Hola, soy Juan Pérez, DNI {MARCADOR_DNI}. Quiero cambiar mi turno."
    assert not r.multiples


def test_dni_de_7_digitos():
    r = anonimizar_dni("mi documento es 7.654.321")
    assert r.dni == "7654321"
    assert r.texto == f"mi documento es {MARCADOR_DNI}"


def test_el_texto_anonimizado_no_contiene_el_dni_en_ninguna_forma():
    r = anonimizar_dni("DNI 30.123.456, repito: 30123456")
    assert "30.123.456" not in r.texto and "30123456" not in r.texto


def test_punto_final_de_oracion():
    r = anonimizar_dni("Mi DNI es 27.345.678.")
    assert r.dni == "27345678"
    assert r.texto == f"Mi DNI es {MARCADOR_DNI}."


def test_sin_dni_el_texto_queda_igual():
    mensaje = "quiero cambiar el turno que tengo, ¿se puede?"
    r = anonimizar_dni(mensaje)
    assert (r.texto, r.dni, r.candidatos) == (mensaje, None, ())


@pytest.mark.parametrize("telefono", ["1544445555", "+54 9 11 4444-5555", "011 4444 5555"])
def test_telefono_no_se_toma_como_dni(telefono):
    r = anonimizar_dni(f"llamame al {telefono}")
    assert r.dni is None and r.candidatos == ()


def test_monto_no_se_toma_como_dni():
    r = anonimizar_dni("¿cuesta $1.200.000 la cirugía?")
    assert r.dni is None


def test_dni_incompleto_no_se_detecta():
    r = anonimizar_dni("DNI 30.123")
    assert r.dni is None
    assert r.texto == "DNI 30.123"  # llega tal cual al LLM (design D6)


def test_horarios_y_fechas_no_son_dni():
    r = anonimizar_dni("turno el 26/11/2026 a las 15:00 hs")
    assert r.candidatos == ()


def test_mismo_dni_repetido_es_un_solo_candidato():
    r = anonimizar_dni("DNI 30.123.456 (30123456)")
    assert r.dni == "30123456"
    assert r.candidatos == ("30123456",)
    assert not r.multiples
    assert r.texto == f"DNI {MARCADOR_DNI} ({MARCADOR_DNI})"


def test_dos_dni_distintos_no_se_elige_ninguno():
    r = anonimizar_dni("Soy 30.123.456 y pido turno para mi mamá, DNI 12.345.678")
    assert r.multiples
    assert r.dni is None
    assert r.candidatos == ("30123456", "12345678")
    # igual se anonimizan los dos: ningún DNI sale hacia la API
    assert "30.123.456" not in r.texto and "12.345.678" not in r.texto
