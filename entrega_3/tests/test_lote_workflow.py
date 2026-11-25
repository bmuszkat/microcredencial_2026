"""
Estructura del lote de casos del workflow (design D12, tarea 5.1).

Estos tests NO corren el workflow: verifican que el lote esté bien armado y sea coherente
con las reglas, antes de la primera corrida real. Que cada caso termine en su estado
esperado lo verifica tests/test_workflow.py (tarea 6.3).
"""

import json
from pathlib import Path

import pytest

from clinica.contrato import INTENCIONES_VALIDAS, contrato_para
from redactor import RespuestaRedactada
from reglas import (COMPLETADO, DERIVADO, PENDIENTE, PRIORIDAD_ESTADOS, REVISION_HUMANA, anonimizar_dni,
                    estado_global)

LOTE = json.loads((Path(__file__).resolve().parents[1] / "datos" / "lote_workflow.json").read_text(encoding="utf-8"))
IDS = [c["id"] for c in LOTE]


def test_son_9_casos_con_ids_unicos():
    assert len(LOTE) == 9
    assert len(set(IDS)) == 9


@pytest.mark.parametrize("caso", LOTE, ids=IDS)
def test_cada_caso_tiene_todos_los_campos(caso):
    assert set(caso) == {"id", "caso", "mensaje", "esperado", "por_que", "simulacion"}
    assert set(caso["esperado"]) == {"estado_global", "intenciones"}
    assert set(caso["simulacion"]) == {"extraccion", "redaccion"}
    assert caso["mensaje"].strip() and caso["por_que"].strip()


@pytest.mark.parametrize("caso", LOTE, ids=IDS)
def test_estados_e_intenciones_validos(caso):
    esperado = caso["esperado"]
    assert esperado["estado_global"] in PRIORIDAD_ESTADOS
    assert esperado["intenciones"], "al menos una intención"
    assert set(esperado["intenciones"]) <= set(INTENCIONES_VALIDAS)
    assert set(esperado["intenciones"].values()) <= set(PRIORIDAD_ESTADOS)


@pytest.mark.parametrize("caso", LOTE, ids=IDS)
def test_estado_global_es_el_mas_restrictivo_de_las_intenciones(caso):
    esperado = caso["esperado"]
    assert estado_global(esperado["intenciones"].values()) == esperado["estado_global"]


def test_cubre_los_dos_casos_minimos_de_a3():
    globales = [c["esperado"]["estado_global"] for c in LOTE]
    assert COMPLETADO in globales        # uno que se completa
    assert REVISION_HUMANA in globales   # uno que se detiene en un punto de control


def test_cubre_todos_los_estados():
    assert {c["esperado"]["estado_global"] for c in LOTE} == set(PRIORIDAD_ESTADOS)


# ── Respuestas simuladas (para correr sin API) ────────────────────────────────

@pytest.mark.parametrize("caso", LOTE, ids=IDS)
def test_la_extraccion_simulada_cumple_el_contrato_y_coincide_con_lo_esperado(caso):
    extraccion = caso["simulacion"]["extraccion"]
    contrato_para("v3")(**extraccion)
    assert extraccion["dni"] is None  # con el DNI anonimizado, el LLM no lo devuelve (prompt v3)
    assert set(extraccion["intenciones"]) == set(caso["esperado"]["intenciones"])


def usa_plantilla(caso: dict) -> bool:
    """Los casos en que el LLM redactor no se llama (design D5)."""
    global_, intenciones = caso["esperado"]["estado_global"], list(caso["esperado"]["intenciones"])
    return (global_ in (REVISION_HUMANA, PENDIENTE)
            or (global_ == DERIVADO and intenciones == ["consulta_medica"])
            or intenciones == ["otra"])


@pytest.mark.parametrize("caso", LOTE, ids=IDS)
def test_hay_redaccion_simulada_solo_si_se_llama_al_redactor(caso):
    redaccion = caso["simulacion"]["redaccion"]
    if usa_plantilla(caso):
        assert redaccion is None
    else:
        RespuestaRedactada(**redaccion)


# ── Mensajes ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("caso", LOTE, ids=IDS)
def test_a_lo_sumo_un_dni_por_mensaje(caso):
    # Ningún caso del lote prueba "varios DNI" (eso lo cubren los tests de reglas).
    assert not anonimizar_dni(caso["mensaje"]).multiples
