"""
Estructura del lote de casos del workflow (Parte A, design D12; Parte B, design D13).

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


MOTIVOS_DE_OTRA = {"rag", "sin_informacion_oficial", "rag_no_verificado"}


def test_son_12_casos_con_ids_unicos():
    assert len(LOTE) == 12   # los 9 de la Parte A y W10 a W12 de la Parte B
    assert len(set(IDS)) == 12


@pytest.mark.parametrize("caso", LOTE, ids=IDS)
def test_cada_caso_tiene_todos_los_campos(caso):
    assert set(caso) == {"id", "caso", "mensaje", "esperado", "por_que", "simulacion"}
    assert set(caso["esperado"]) <= {"estado_global", "intenciones", "motivos"}
    assert {"estado_global", "intenciones"} <= set(caso["esperado"])
    assert set(caso["simulacion"]) == {"extraccion", "redaccion", "rag"}
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
    contrato_para("v4")(**extraccion)
    assert extraccion["dni"] is None  # con el DNI anonimizado, el LLM no lo devuelve (prompts v3 y v4)
    assert set(extraccion["intenciones"]) == set(caso["esperado"]["intenciones"])


def usa_plantilla(caso: dict) -> bool:
    """Los casos en que el LLM redactor no se llama (design D5)."""
    global_, intenciones = caso["esperado"]["estado_global"], list(caso["esperado"]["intenciones"])
    return (global_ in (REVISION_HUMANA, PENDIENTE)
            or (global_ == DERIVADO and intenciones == ["consulta_medica"])
            or intenciones == ["otra"])   # 'otra' la responde el RAG, no el redactor


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


# ── Parte B: 'otra' pasa por el RAG (design D13) ──────────────────────────────

@pytest.mark.parametrize("caso", LOTE, ids=IDS)
def test_motivo_esperado_solo_para_otra(caso):
    motivos = caso["esperado"].get("motivos", {})
    assert set(motivos) <= {"otra"}
    assert set(motivos.values()) <= MOTIVOS_DE_OTRA
    if "otra" in caso["esperado"]["intenciones"]:
        assert "otra" in motivos, "cada caso con 'otra' fija qué tiene que hacer el RAG"


@pytest.mark.parametrize("caso", LOTE, ids=IDS)
def test_rag_simulado_solo_para_otra_y_coherente_con_el_motivo(caso):
    rag = caso["simulacion"]["rag"]
    if list(caso["esperado"]["intenciones"]) != ["otra"]:
        assert rag is None
        return
    assert set(rag) == {"estado", "texto", "citas"}
    motivo = caso["esperado"]["motivos"]["otra"]
    estado_rag = {"rag": "respondida", "sin_informacion_oficial": "sin_informacion"}[motivo]
    assert rag["estado"] == estado_rag
    assert bool(rag["citas"]) == (motivo == "rag")
    assert all(f"({c})" in rag["texto"] for c in rag["citas"])


def test_cubre_los_resultados_del_rag_y_el_limite_del_v4():
    motivos = [c["esperado"].get("motivos", {}).get("otra") for c in LOTE]
    assert "rag" in motivos and "sin_informacion_oficial" in motivos
    w12 = next(c for c in LOTE if c["id"] == "W12")
    assert w12["esperado"]["intenciones"] == {"consulta_medica": "DERIVADO"}
    assert "fondo de ojo" in w12["mensaje"].lower()
