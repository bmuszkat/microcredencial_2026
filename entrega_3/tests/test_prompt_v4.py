"""
El prompt de extracción v4 (design D12): el v3 más el límite entre una indicación publicada
de la clínica ("otra", la responde el RAG) y una duda clínica ("consulta_medica", se deriva).
"""

import json
import re
from pathlib import Path

import pytest

from clinica.contrato import INTENCIONES_VALIDAS, contrato_para
from reglas import MARCADOR_DNI, anonimizar_dni

ENTREGA_3 = Path(__file__).resolve().parents[1]
ENTREGA_2 = ENTREGA_3.parent / "entrega_2"
PROMPTS = ENTREGA_3 / "prompts"
PROMPT = (PROMPTS / "extraccion_v4.txt").read_text(encoding="utf-8")


def ejemplos(prompt: str) -> list[tuple[str, dict]]:
    mensajes = re.findall(r'^Mensaje: "(.*)"$', prompt, flags=re.MULTILINE)
    jsons = [json.loads(j) for j in re.findall(r"^JSON: (\{.*\})$", prompt, flags=re.MULTILINE)]
    assert len(mensajes) == len(jsons) > 0, "cada ejemplo tiene que tener su mensaje y su JSON"
    return list(zip(mensajes, jsons))


EJEMPLOS = ejemplos(PROMPT)
POR_MENSAJE = dict(EJEMPLOS)


# ── Los mismos chequeos que el v3 ─────────────────────────────────────────────

def test_v4_valida_contra_el_contrato_de_v2():
    assert contrato_para("v4") is contrato_para("v2")


@pytest.mark.parametrize("mensaje, ejemplo", EJEMPLOS, ids=[m[:40] for m, _ in EJEMPLOS])
def test_cada_ejemplo_cumple_el_contrato(mensaje, ejemplo):
    contrato_para("v4")(**ejemplo)


def test_las_intenciones_del_prompt_son_exactamente_las_del_contrato():
    del_prompt = re.findall(r"^\s{4}(\w+)\s+→", PROMPT, flags=re.MULTILINE)
    assert sorted(del_prompt) == sorted(INTENCIONES_VALIDAS)


def test_todas_las_claves_del_contrato_estan_en_el_prompt():
    assert not [c for c in contrato_para("v4").model_fields if f'"{c}"' not in PROMPT]


def test_sin_dni_en_claro_y_con_el_marcador():
    assert anonimizar_dni(PROMPT).candidatos == ()
    assert all(e["dni"] is None for _, e in EJEMPLOS)
    assert sum(MARCADOR_DNI in m for m, _ in EJEMPLOS) >= 2


def test_otra_nunca_se_combina():
    assert all(e["intenciones"] == ["otra"] for _, e in EJEMPLOS if "otra" in e["intenciones"])


def test_ningun_ejemplo_coincide_con_un_mensaje_de_evaluacion():
    usados = {m["mensaje"] for m in json.loads((ENTREGA_2 / "datos" / "set_evaluacion.json").read_text(encoding="utf-8"))}
    usados |= {c["mensaje"] for c in json.loads((ENTREGA_2 / "datos" / "lote_prueba.json").read_text(encoding="utf-8"))}
    usados |= {c["mensaje"] for c in json.loads((ENTREGA_3 / "datos" / "lote_workflow.json").read_text(encoding="utf-8"))}
    usados |= {p["pregunta"] for p in json.loads((ENTREGA_3 / "datos" / "preguntas_comparacion.json").read_text(encoding="utf-8"))["preguntas"]}
    assert not [m for m, _ in EJEMPLOS if m in usados]


# ── Lo nuevo del v4 ───────────────────────────────────────────────────────────

def test_manejar_despues_de_dilatar_es_otra():
    assert POR_MENSAJE["¿Puedo manejar después de que me dilaten las pupilas?"]["intenciones"] == ["otra"]


def test_un_sintoma_despues_de_un_estudio_sigue_siendo_consulta_medica():
    sintoma = [e for m, e in EJEMPLOS if "dilataron" in m and "nublada" in m]
    assert sintoma and sintoma[0]["intenciones"] == ["consulta_medica"]


def test_la_regla_del_limite_esta_escrita():
    assert re.search(r"indicación general que publica la clínica", PROMPT)
    assert "cómo prepararse para un estudio" in PROMPT


def test_el_v4_es_el_v3_mas_los_cambios_del_limite():
    """
    Todo lo del v3 sigue en el v4 salvo las descripciones de consulta_medica y otra. (El JSON del
    ejemplo de manejar en el v3 sigue apareciendo en el v4: es igual al del ejemplo nuevo de síntoma.)
    """
    v3 = (PROMPTS / "extraccion_v3.txt").read_text(encoding="utf-8").splitlines()
    v4 = PROMPT.splitlines()
    cambiadas = [linea for linea in v3 if linea not in v4]
    assert [linea.split()[0] for linea in cambiadas] == ["consulta_medica", "otra"]
    assert len(v4) - len(v3) == 6   # la regla 8 (3 renglones) y el ejemplo de síntoma (3 con el blanco)


def test_el_v3_queda_sin_cambios():
    """La corrida de la Parte A tiene que seguir siendo reproducible con el v3."""
    v3 = dict(ejemplos((PROMPTS / "extraccion_v3.txt").read_text(encoding="utf-8")))
    assert v3["¿Puedo manejar después de que me dilaten las pupilas?"]["intenciones"] == ["consulta_medica"]
    assert "indicación general que publica la clínica" not in (PROMPTS / "extraccion_v3.txt").read_text(encoding="utf-8")
