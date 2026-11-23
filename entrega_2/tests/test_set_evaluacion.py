"""El set de evaluación (spec `evaluacion-extraccion`) está bien armado. No usa la API."""

import json
import re
from collections import Counter

import pytest

from clinica.config import RAIZ_ENTREGA
from clinica.contrato import INTENCIONES_VALIDAS, ExtraccionPaciente

SET = json.loads((RAIZ_ENTREGA / "datos" / "set_evaluacion.json").read_text(encoding="utf-8"))
LOTE = json.loads((RAIZ_ENTREGA / "datos" / "lote_prueba.json").read_text(encoding="utf-8"))
CATEGORIAS = {"simple", "multi", "ambiguo", "medica", "mixto", "fuera_de_alcance", "manipulacion"}


def test_tiene_50_mensajes_con_ids_unicos():
    assert len(SET) == 50
    assert len({caso["id"] for caso in SET}) == 50


def test_mensajes_sin_repetir():
    assert len({caso["mensaje"] for caso in SET}) == 50


def test_categorias_validas_y_todas_presentes():
    assert {caso["categoria"] for caso in SET} == CATEGORIAS


@pytest.mark.parametrize("caso", SET, ids=lambda c: c["id"])
def test_cada_etiqueta_cumple_el_contrato_vigente(caso):
    ExtraccionPaciente(**caso["esperado"])


@pytest.mark.parametrize("caso", [c for c in SET if c["esperado"]["dni"]], ids=lambda c: c["id"])
def test_el_dni_esperado_esta_en_el_mensaje(caso):
    digitos = re.sub(r"\D", "", caso["mensaje"])
    assert caso["esperado"]["dni"] in digitos


def test_cada_intencion_aparece_al_menos_3_veces():
    cuenta = Counter(i for caso in SET for i in caso["esperado"]["intenciones"])
    for intencion in INTENCIONES_VALIDAS:
        assert cuenta[intencion] >= 3, intencion


def test_ningun_mensaje_es_un_ejemplo_de_los_prompts_ni_del_lote():
    """Si un mensaje estuviera en el few-shot o en el lote, la medición estaría inflada."""
    prompts = " ".join(p.read_text(encoding="utf-8") for p in (RAIZ_ENTREGA / "prompts").glob("*.txt"))
    mensajes_lote = {caso["mensaje"] for caso in LOTE}
    for caso in SET:
        assert caso["mensaje"] not in prompts, caso["id"]
        assert caso["mensaje"] not in mensajes_lote, caso["id"]
