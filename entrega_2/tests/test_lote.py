"""El lote de prueba tiene los 4 tipos que pide la consigna y simulaciones válidas."""

import json

from clinica.config import RAIZ_ENTREGA
from clinica.extractor import validar_respuesta

LOTE = json.loads((RAIZ_ENTREGA / "datos" / "lote_prueba.json").read_text(encoding="utf-8"))


def test_el_lote_tiene_los_4_tipos_de_la_consigna():
    assert [caso["tipo"] for caso in LOTE] == ["Típico", "Ambiguo", "Manipulación", "Caso límite"]


def test_cada_caso_tiene_los_campos_necesarios():
    for caso in LOTE:
        assert {"tipo", "mensaje", "observar", "simulacion"} <= caso.keys()


def test_las_simulaciones_cumplen_el_contrato():
    for caso in LOTE:
        assert validar_respuesta(caso["simulacion"])["ok"], caso["tipo"]


def test_los_mensajes_del_lote_no_son_ejemplos_del_prompt():
    """Si un mensaje del lote estuviera en el few-shot, el resultado estaría inflado (design D7)."""
    prompt = (RAIZ_ENTREGA / "prompts" / "extraccion_v1.txt").read_text(encoding="utf-8")
    for caso in LOTE:
        assert caso["mensaje"] not in prompt
