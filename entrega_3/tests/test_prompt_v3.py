"""El prompt de extracción v3 (design D14) tiene que coincidir con el contrato y no filtrar datos."""

import json
import re
from pathlib import Path

import pytest

from clinica.contrato import INTENCIONES_VALIDAS, contrato_para
from reglas import MARCADOR_DNI, anonimizar_dni

ENTREGA_3 = Path(__file__).resolve().parents[1]
ENTREGA_2 = ENTREGA_3.parent / "entrega_2"
PROMPT = (ENTREGA_3 / "prompts" / "extraccion_v3.txt").read_text(encoding="utf-8")


def ejemplos() -> list[tuple[str, dict]]:
    mensajes = re.findall(r'^Mensaje: "(.*)"$', PROMPT, flags=re.MULTILINE)
    jsons = [json.loads(j) for j in re.findall(r"^JSON: (\{.*\})$", PROMPT, flags=re.MULTILINE)]
    assert len(mensajes) == len(jsons) > 0, "cada ejemplo tiene que tener su mensaje y su JSON"
    return list(zip(mensajes, jsons))


EJEMPLOS = ejemplos()


# ── Coincidencia con el contrato ──────────────────────────────────────────────

def test_v3_valida_contra_el_contrato_de_v2():
    assert contrato_para("v3") is contrato_para("v2")


@pytest.mark.parametrize("mensaje, ejemplo", EJEMPLOS, ids=[m[:40] for m, _ in EJEMPLOS])
def test_cada_ejemplo_cumple_el_contrato(mensaje, ejemplo):
    contrato_para("v3")(**ejemplo)


def test_las_intenciones_del_prompt_son_exactamente_las_del_contrato():
    # La lista de valores posibles: renglones con sangría "    <intencion>   → descripción".
    del_prompt = re.findall(r"^\s{4}(\w+)\s+→", PROMPT, flags=re.MULTILINE)
    assert sorted(del_prompt) == sorted(INTENCIONES_VALIDAS)


def test_todas_las_claves_del_contrato_estan_en_el_prompt():
    faltantes = [c for c in contrato_para("v3").model_fields if f'"{c}"' not in PROMPT]
    assert not faltantes


# ── Privacidad: el DNI no aparece en claro ────────────────────────────────────

def test_ningun_ejemplo_trae_un_dni_en_claro():
    assert anonimizar_dni(PROMPT).candidatos == ()


def test_los_ejemplos_devuelven_dni_null():
    assert all(ejemplo["dni"] is None for _, ejemplo in EJEMPLOS)


def test_hay_ejemplos_con_el_marcador_dni():
    assert sum(MARCADOR_DNI in mensaje for mensaje, _ in EJEMPLOS) >= 2


# ── Los dos fallos de la evaluación de la Entrega 2 ───────────────────────────

def test_ejemplo_con_la_fecha_de_un_estudio_sin_fechas_de_turno():
    """s12: la fecha en que se hizo el estudio no va en los campos de turno."""
    con_estudio = [e for m, e in EJEMPLOS if "consultar_resultado" in e["intenciones"] and "pasado" in m]
    assert con_estudio
    assert all(e["fecha_turno_actual"] is None and e["fecha_deseada"] is None for e in con_estudio)


def test_profesional_es_un_nombre_de_la_clinica_o_null():
    """p02 y el ejemplo del v2: ni un paciente ni una descripción ('el doctor que me operó')."""
    for _, ejemplo in EJEMPLOS:
        profesional = ejemplo["profesional"]
        assert profesional is None or profesional.split()[0] in ("Dr.", "Dra."), profesional


def test_ejemplo_con_un_familiar_que_no_es_profesional():
    familiar = [e for m, e in EJEMPLOS if "Raúl Medina" in m]
    assert familiar and familiar[0]["profesional"] == "Dra. Paz"


# ── Ningún ejemplo es un mensaje con el que se evalúa ─────────────────────────

def mensajes_de_evaluacion() -> set[str]:
    usados = {m["mensaje"] for m in json.loads((ENTREGA_2 / "datos" / "set_evaluacion.json").read_text(encoding="utf-8"))}
    usados |= {c["mensaje"] for c in json.loads((ENTREGA_2 / "datos" / "lote_prueba.json").read_text(encoding="utf-8"))}
    lote_e3 = ENTREGA_3 / "datos" / "lote_workflow.json"  # existe a partir de la tarea 5.1
    if lote_e3.exists():
        usados |= {c["mensaje"] for c in json.loads(lote_e3.read_text(encoding="utf-8"))}
    return usados


def test_ningun_ejemplo_coincide_con_un_mensaje_de_evaluacion():
    usados = mensajes_de_evaluacion()
    repetidos = [m for m, _ in EJEMPLOS if m in usados]
    assert not repetidos
