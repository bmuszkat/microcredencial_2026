"""Sensores de solo lectura (spec `agenda-clinica`): un test por escenario y la garantía de que no escriben."""

import copy
import json
import shutil
from datetime import date, datetime
from pathlib import Path

import pytest

import herramientas as h

DATOS = Path(__file__).resolve().parents[1] / "datos"


@pytest.fixture
def datos():
    return h.cargar_datos()


# ── Fecha de referencia ───────────────────────────────────────────────────────

def test_ahora_es_la_fecha_de_referencia_y_no_el_reloj(datos):
    assert h.ahora(datos) == datetime(2026, 11, 24, 10, 0)


def test_turno_pasado_no_aparece_entre_los_futuros(datos):
    # Roberto Sosa solo tiene un turno el 20/11, anterior a la referencia.
    assert h.turnos_futuros("20444555", datos) == []


def test_turnos_futuros_ordenados(datos):
    turnos = h.turnos_futuros("28999111", datos)
    assert [(t["fecha"], t["hora"]) for t in turnos] == [("2026-11-27", "09:00"), ("2026-12-03", "11:00")]


# ── Paciente ──────────────────────────────────────────────────────────────────

def test_paciente_existente(datos):
    assert h.buscar_paciente("30123456", datos)["nombre"] == "Juan Pérez"


def test_paciente_inexistente_devuelve_none_sin_error(datos):
    assert h.buscar_paciente("40111222", datos) is None
    assert h.buscar_paciente(None, datos) is None


# ── Estudios ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nombre", ["campo visual", "Campo Visual", "el campo visual", "CAMPO VISUAL"])
def test_estudio_por_nombre_aproximado(datos, nombre):
    encontrados = h.buscar_estudios("30123456", nombre, datos)
    assert [e["id"] for e in encontrados] == ["E-001"]


def test_estudio_con_tilde(datos):
    assert [e["id"] for e in h.buscar_estudios("35777888", "topografia", datos)] == ["E-007"]


def test_estudio_que_el_paciente_no_tiene(datos):
    assert h.buscar_estudios("30123456", "OCT", datos) == []


def test_palabras_completas_oct_no_coincide_con_doctor(datos):
    assert h.buscar_estudios("31456789", "el doctor", datos) == []


def test_sin_nombre_devuelve_todos_los_estudios_del_paciente(datos):
    assert {e["id"] for e in h.buscar_estudios("33222111", None, datos)} == {"E-005", "E-006"}


# ── Turnos libres ─────────────────────────────────────────────────────────────

def test_turnos_libres_filtrados_por_fecha_franja_y_profesional(datos):
    viernes = date(2026, 11, 27)
    libres = h.turnos_libres(viernes, viernes, ("08:00", "13:00"), "Dra. López", datos)
    assert [(t["profesional"], t["fecha"], t["hora"]) for t in libres] == [
        ("Dra. López", "2026-11-27", "09:00"),
        ("Dra. López", "2026-11-27", "10:30"),
        ("Dra. López", "2026-11-27", "12:00"),
    ]


def test_turnos_libres_sin_profesional_incluye_a_todos(datos):
    viernes = date(2026, 11, 27)
    libres = h.turnos_libres(viernes, viernes, ("08:00", "13:00"), None, datos)
    assert {t["profesional"] for t in libres} == {"Dra. López", "Dra. Ríos"}
    assert libres == sorted(libres, key=lambda t: (t["fecha"], t["hora"]))


def test_turno_reservado_no_aparece_como_libre(datos):
    # La Dra. Ríos tiene reservado el viernes 27/11 a las 09:00 (Carlos Díaz).
    viernes = date(2026, 11, 27)
    libres = h.turnos_libres(viernes, viernes, None, "Dra. Ríos", datos)
    assert "09:00" not in [t["hora"] for t in libres]


def test_franja_sin_turnos(datos):
    lunes = date(2026, 11, 30)
    assert h.turnos_libres(lunes, lunes, ("13:00", "19:00"), "Dr. Ruiz", datos) == []


@pytest.mark.parametrize("mencionado", ["la doctora Lopez", "López", "Dra. López", "dra lopez"])
def test_profesional_mencionado_por_apellido(mencionado):
    assert h.coincide_profesional(mencionado, "Dra. López")


def test_profesional_distinto_no_coincide():
    assert not h.coincide_profesional("Dr. Ruiz", "Dra. López")


def test_datos_del_profesional(datos):
    assert h.datos_profesional("la doctora López", datos) == {
        "nombre": "Dra. López", "especialidad": "Glaucoma", "sede": "Centro"}


# ── Política de cargos ────────────────────────────────────────────────────────

def test_politica_de_cargos(datos):
    politica = h.politica_cargos(datos)
    assert (politica["umbral_horas"], politica["monto"]) == (24, 12000)


def test_cambio_de_politica_sin_tocar_codigo(tmp_path):
    copia = tmp_path / "datos"
    shutil.copytree(DATOS, copia)
    archivo = copia / "politica_cargos.json"
    politica = json.loads(archivo.read_text(encoding="utf-8"))
    politica["monto"] = 15000
    archivo.write_text(json.dumps(politica), encoding="utf-8")
    assert h.politica_cargos(h.cargar_datos(copia))["monto"] == 15000


# ── Solo lectura ──────────────────────────────────────────────────────────────

def test_ninguna_consulta_modifica_los_datos(datos):
    antes = copy.deepcopy(datos)
    resultados = [
        h.buscar_paciente("30123456", datos),
        h.turnos_futuros("28999111", datos),
        h.buscar_estudios("33222111", None, datos),
        h.turnos_libres(date(2026, 11, 24), date(2026, 12, 4), None, None, datos),
        h.datos_profesional("López", datos),
        h.politica_cargos(datos),
    ]
    # Aunque quien llama modifique lo que recibe, el backend no cambia.
    resultados[0]["nombre"] = "otro"
    resultados[1][0]["hora"] = "00:00"
    resultados[2].clear()
    resultados[3][0]["fecha"] = "1900-01-01"
    resultados[5]["monto"] = 0
    assert datos == antes


def test_datos_por_defecto_se_leen_de_la_carpeta_datos():
    assert h.buscar_paciente("30123456")["nombre"] == "Juan Pérez"
