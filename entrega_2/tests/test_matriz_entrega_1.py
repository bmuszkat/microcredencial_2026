"""Las intenciones del contrato vigente coinciden con la Matriz de la Entrega 1 (consigna E2, criterio 1)."""

import re

from clinica.config import RAIZ_REPO
from clinica.contrato import INTENCIONES_VALIDAS

INFORME_E1 = (RAIZ_REPO / "entrega_1" / "informe.md").read_text(encoding="utf-8")


def test_intenciones_de_la_matriz_b4_coinciden_con_el_contrato():
    b4 = INFORME_E1[INFORME_E1.index("### B.4"):INFORME_E1.index("### B.5")]
    intenciones_matriz = set(re.findall(r"^\|[^|]*\| `([a-z_]+)` \|", b4, flags=re.MULTILINE))
    assert intenciones_matriz == set(INTENCIONES_VALIDAS)


def test_alcance_b3_lista_todas_las_intenciones():
    b3 = INFORME_E1[INFORME_E1.index("### B.3"):INFORME_E1.index("### B.4")]
    for intencion in INTENCIONES_VALIDAS:
        assert f"`{intencion}`" in b3, intencion
