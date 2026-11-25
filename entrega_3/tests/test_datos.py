"""Consistencia de los datos ficticios del backend (spec `agenda-clinica`, design D8)."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

DATOS = Path(__file__).resolve().parents[1] / "datos"


def cargar(nombre: str) -> dict:
    return json.loads((DATOS / nombre).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def padron():
    return cargar("padron.json")["pacientes"]


@pytest.fixture(scope="module")
def agenda():
    return cargar("agenda.json")


@pytest.fixture(scope="module")
def estudios():
    return cargar("estudios.json")["estudios"]


@pytest.fixture(scope="module")
def ahora(agenda):
    return datetime.fromisoformat(agenda["fecha_referencia"])


def momento(turno: dict) -> datetime:
    return datetime.fromisoformat(f"{turno['fecha']}T{turno['hora']}")


# ── Estructura y referencias ──────────────────────────────────────────────────

def test_dnis_del_padron_son_unicos_y_validos(padron):
    dnis = [p["dni"] for p in padron]
    assert len(dnis) == len(set(dnis))
    assert all(d.isdigit() and len(d) in (7, 8) for d in dnis)


def test_fecha_referencia_es_martes_24_11_a_las_10(ahora):
    assert ahora == datetime(2026, 11, 24, 10, 0)
    assert ahora.weekday() == 1


def test_turnos_reservados_referencian_pacientes_y_profesionales(agenda, padron):
    dnis = {p["dni"] for p in padron}
    profesionales = {p["nombre"] for p in agenda["profesionales"]}
    for t in agenda["turnos_reservados"]:
        assert t["dni"] in dnis, t
        assert t["profesional"] in profesionales, t


def test_turnos_libres_referencian_profesionales(agenda):
    profesionales = {p["nombre"] for p in agenda["profesionales"]}
    assert all(t["profesional"] in profesionales for t in agenda["turnos_libres"])


def test_estudios_referencian_pacientes_y_tienen_estado_valido(estudios, padron):
    dnis = {p["dni"] for p in padron}
    for e in estudios:
        assert e["dni"] in dnis, e
        assert e["estado"] in ("listo", "en_proceso", "pendiente"), e
        # un estudio pendiente todavía no se realizó
        assert (e["fecha_realizacion"] is None) == (e["estado"] == "pendiente"), e


def test_ids_unicos(agenda, estudios):
    ids_turnos = [t["id"] for t in agenda["turnos_reservados"]]
    ids_estudios = [e["id"] for e in estudios]
    assert len(ids_turnos) == len(set(ids_turnos))
    assert len(ids_estudios) == len(set(ids_estudios))


def test_ningun_turno_libre_y_reservado_a_la_vez(agenda):
    clave = lambda t: (t["profesional"], t["fecha"], t["hora"])  # noqa: E731
    reservados = {clave(t) for t in agenda["turnos_reservados"]}
    libres = [clave(t) for t in agenda["turnos_libres"]]
    assert not reservados & set(libres)
    assert len(libres) == len(set(libres))  # tampoco hay libres repetidos


def test_turnos_libres_son_futuros(agenda, ahora):
    assert all(momento(t) > ahora for t in agenda["turnos_libres"])


def test_politica_de_cargos():
    politica = cargar("politica_cargos.json")
    assert politica["umbral_horas"] == 24
    assert politica["monto"] == 12000
    assert set(politica["aplica_a"]) == {"modificar_turno", "cancelar_turno"}


# ── Lo que necesita cada caso del lote (design D12) ───────────────────────────

def test_juan_perez_tiene_su_turno_del_jueves_y_su_campo_visual(padron, agenda, estudios):
    assert any(p["dni"] == "30123456" and p["nombre"] == "Juan Pérez" for p in padron)
    turnos = [t for t in agenda["turnos_reservados"] if t["dni"] == "30123456"]
    assert [(t["profesional"], t["fecha"], t["hora"]) for t in turnos] == [("Dra. López", "2026-11-26", "15:00")]
    assert date.fromisoformat("2026-11-26").weekday() == 3  # jueves
    campo_visual = [e for e in estudios if e["dni"] == "30123456" and e["estudio"] == "campo visual"]
    assert campo_visual and campo_visual[0]["estado"] == "listo"


def test_hay_turnos_libres_el_viernes_27_a_la_manana_con_la_dra_lopez(agenda):
    libres = [t for t in agenda["turnos_libres"]
              if t["profesional"] == "Dra. López" and t["fecha"] == "2026-11-27" and "08:00" <= t["hora"] < "13:00"]
    assert len(libres) >= 2


def test_hay_un_turno_a_menos_de_24_horas(agenda, ahora):
    cercanos = [t for t in agenda["turnos_reservados"] if ahora < momento(t) < ahora + timedelta(hours=24)]
    assert [(t["dni"], t["fecha"], t["hora"]) for t in cercanos] == [("25678901", "2026-11-25", "09:00")]


def test_un_paciente_tiene_dos_turnos_futuros_con_la_misma_profesional(agenda, ahora):
    futuros = [t for t in agenda["turnos_reservados"] if t["dni"] == "28999111" and momento(t) > ahora]
    assert len(futuros) == 2
    assert {t["profesional"] for t in futuros} == {"Dra. Ríos"}


def test_hay_un_turno_pasado(agenda, ahora):
    assert any(momento(t) < ahora for t in agenda["turnos_reservados"])


def test_dni_del_caso_fuera_del_padron_no_esta(padron):
    assert "40111222" not in {p["dni"] for p in padron}


def test_paciente_para_turno_nuevo_y_libres_la_semana_que_viene(padron, agenda):
    assert any(p["dni"] == "31456789" for p in padron)
    semana_que_viene = [t for t in agenda["turnos_libres"]
                        if t["profesional"] == "Dr. Ruiz" and "2026-11-30" <= t["fecha"] <= "2026-12-04"]
    assert semana_que_viene


def test_un_paciente_tiene_varios_estudios(estudios):
    por_dni = {}
    for e in estudios:
        por_dni.setdefault(e["dni"], []).append(e)
    assert any(len(lista) > 1 for lista in por_dni.values())
