"""
Reglas del dominio de la Entrega 3 (reglas.py).

Se llama test_reglas_dominio.py y no test_reglas.py porque la Entrega 2 ya tiene un
tests/test_reglas.py y pytest no admite dos módulos de test con el mismo nombre.
"""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from reglas import (COMPLETADO, DERIVADO, FRANJA_MANANA, FRANJA_TARDE, MARCADOR_DNI, PENDIENTE,
                    PENDIENTE_CONFIRMACION, REVISION_HUMANA, FechaConvertida, anonimizar_dni, calcular_cargo,
                    convertir_fecha, estado_global)

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


# ── Paso 6 · Convertir fechas relativas ───────────────────────────────────────

REFERENCIA = datetime(2026, 11, 24, 10, 0)  # martes 24/11/2026 a las 10:00 (agenda.json)


def un_dia(d: str, franja=None, hora=None) -> FechaConvertida:
    dia = date.fromisoformat(d)
    return FechaConvertida(desde=dia, hasta=dia, franja=franja, hora=hora)


@pytest.mark.parametrize("texto, esperado", [
    # el caso del journey: "a la mañana" es una franja, no el día siguiente
    ("viernes a la mañana", un_dia("2026-11-27", franja=FRANJA_MANANA)),
    ("el viernes por la mañana", un_dia("2026-11-27", franja=FRANJA_MANANA)),
    ("jueves a las 15 hs", un_dia("2026-11-26", hora="15:00")),
    ("jueves 15 hs", un_dia("2026-11-26", hora="15:00")),
    ("el jueves a las 15", un_dia("2026-11-26", hora="15:00")),
    ("lunes a la tarde", un_dia("2026-11-30", franja=FRANJA_TARDE)),
    ("el miércoles", un_dia("2026-11-25")),
    ("miercoles", un_dia("2026-11-25")),
    ("el martes", un_dia("2026-11-24")),           # hoy es martes: desde hoy inclusive
    ("hoy a la tarde", un_dia("2026-11-24", franja=FRANJA_TARDE)),
    ("mañana", un_dia("2026-11-25")),
    ("mañana a la mañana", un_dia("2026-11-25", franja=FRANJA_MANANA)),
    ("mañana a las 9:30", un_dia("2026-11-25", hora="09:30")),
    ("pasado mañana", un_dia("2026-11-26")),
    ("27/11", un_dia("2026-11-27")),
    ("el 3/12 a las 11 hs", un_dia("2026-12-03", hora="11:00")),
    ("viernes 27/11", un_dia("2026-11-27")),
    ("el viernes a las 3 de la tarde", un_dia("2026-11-27", hora="15:00")),
    ("el miércoles de la semana que viene", un_dia("2026-12-02")),
])
def test_fechas_de_un_dia(texto, esperado):
    assert convertir_fecha(texto, REFERENCIA) == esperado


@pytest.mark.parametrize("texto", ["la semana que viene", "la próxima semana", "semana próxima"])
def test_semana_que_viene_es_lunes_a_viernes_de_la_siguiente(texto):
    r = convertir_fecha(texto, REFERENCIA)
    assert (r.desde, r.hasta) == (date(2026, 11, 30), date(2026, 12, 4))
    assert not r.un_solo_dia


def test_semana_que_viene_con_franja():
    r = convertir_fecha("la semana que viene a la tarde", REFERENCIA)
    assert (r.desde, r.hasta, r.franja) == (date(2026, 11, 30), date(2026, 12, 4), FRANJA_TARDE)


@pytest.mark.parametrize("texto", [
    "cuando pueda",
    "lo antes posible",
    "a la mañana",            # franja sin día
    "a las 9",                # hora sin día
    "lunes o martes",         # dos días: no se elige por el paciente
    "jueves 27/11",           # el 27/11 es viernes: contradictorio
    "31/02",                  # fecha imposible
    "el viernes a las 25 hs",  # hora imposible
    "",
    None,
])
def test_fecha_que_no_se_entiende(texto):
    assert convertir_fecha(texto, REFERENCIA) is None


def test_la_conversion_depende_de_la_referencia_no_del_reloj():
    # Con la referencia un jueves, "el viernes" es el día siguiente.
    otra = datetime(2026, 12, 3, 10, 0)
    assert convertir_fecha("el viernes", otra) == un_dia("2026-12-04")
    assert convertir_fecha("mañana", otra) == un_dia("2026-12-04")


# ── Paso 8 · Cargo por reprogramar o cancelar con poca anticipación ───────────

POLITICA = json.loads((Path(__file__).resolve().parents[1] / "datos" / "politica_cargos.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("turno, cargo", [
    (datetime(2026, 11, 25, 9, 0), 12000),    # 23 h antes: el caso 8 del lote
    (datetime(2026, 11, 25, 9, 59), 12000),   # 23 h 59 min
    (datetime(2026, 11, 25, 10, 0), 0),       # exactamente 24 h: no hay cargo
    (datetime(2026, 11, 26, 15, 0), 0),       # el turno de Juan Pérez: más de 24 h
])
def test_cargo_segun_la_anticipacion(turno, cargo):
    assert calcular_cargo("modificar_turno", turno, REFERENCIA, POLITICA) == cargo


def test_cargo_tambien_aplica_a_cancelar():
    assert calcular_cargo("cancelar_turno", datetime(2026, 11, 25, 9, 0), REFERENCIA, POLITICA) == 12000


@pytest.mark.parametrize("intencion", ["crear_turno", "consultar_disponibilidad", "consultar_resultado"])
def test_cargo_no_aplica_a_otras_intenciones(intencion):
    assert calcular_cargo(intencion, datetime(2026, 11, 25, 9, 0), REFERENCIA, POLITICA) == 0


def test_cargo_lee_umbral_y_monto_de_la_politica():
    otra = {**POLITICA, "umbral_horas": 48, "monto": 20000}
    assert calcular_cargo("modificar_turno", datetime(2026, 11, 26, 9, 0), REFERENCIA, otra) == 20000


# ── Estado global ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("estados, esperado", [
    ([PENDIENTE_CONFIRMACION, COMPLETADO], PENDIENTE_CONFIRMACION),   # Juan: reprogramar + resultado
    ([PENDIENTE_CONFIRMACION, DERIVADO], PENDIENTE_CONFIRMACION),     # turno nuevo + síntoma
    ([DERIVADO, COMPLETADO], DERIVADO),
    ([PENDIENTE, PENDIENTE_CONFIRMACION, COMPLETADO], PENDIENTE),
    ([COMPLETADO, REVISION_HUMANA, PENDIENTE], REVISION_HUMANA),
    ([DERIVADO], DERIVADO),
    ([COMPLETADO], COMPLETADO),
])
def test_estado_global_es_el_mas_restrictivo(estados, esperado):
    assert estado_global(estados) == esperado


def test_estado_global_no_depende_del_orden():
    assert estado_global([COMPLETADO, PENDIENTE]) == estado_global([PENDIENTE, COMPLETADO]) == PENDIENTE


@pytest.mark.parametrize("estados", [[], ["APROBADO"]])
def test_estado_global_rechaza_vacio_o_desconocido(estados):
    with pytest.raises(ValueError):
        estado_global(estados)
