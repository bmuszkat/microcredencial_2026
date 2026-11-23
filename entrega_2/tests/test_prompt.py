"""El prompt y el contrato tienen que coincidir (riesgo del design: que diverjan)."""

import json
import re
from pathlib import Path
from typing import get_args

import pytest

from clinica.contrato import contrato_para

# Todos los prompts (v1, v2, …, zeroshot) tienen que respetar el contrato.
PROMPTS = sorted((Path(__file__).resolve().parents[1] / "prompts").glob("extraccion_*.txt"))
# Los prompts versionados (v1, v2, …) son few-shot: tienen ejemplos.
# Cada prompt se compara contra el contrato de SU versión (extraccion_v1 → contrato v1).
PROMPTS_FEW_SHOT = [p for p in PROMPTS if p.stem.startswith("extraccion_v")]


def version_de(ruta: Path) -> str:
    return ruta.stem.removeprefix("extraccion_")


def intenciones_del_contrato(ruta: Path) -> tuple[str, ...]:
    campo = contrato_para(version_de(ruta)).model_fields["intenciones"]
    return get_args(get_args(campo.annotation)[0])


@pytest.mark.parametrize("ruta", PROMPTS, ids=lambda p: p.stem)
def test_todas_las_intenciones_del_contrato_estan_en_el_prompt(ruta):
    texto = ruta.read_text(encoding="utf-8")
    faltantes = [i for i in intenciones_del_contrato(ruta) if i not in texto]
    assert not faltantes, f"El prompt {ruta.name} no menciona: {faltantes}"


@pytest.mark.parametrize("ruta", PROMPTS, ids=lambda p: p.stem)
def test_todas_las_claves_del_contrato_estan_en_el_prompt(ruta):
    texto = ruta.read_text(encoding="utf-8")
    faltantes = [c for c in contrato_para(version_de(ruta)).model_fields if f'"{c}"' not in texto]
    assert not faltantes, f"El prompt {ruta.name} no define: {faltantes}"


@pytest.mark.parametrize("ruta", PROMPTS_FEW_SHOT, ids=lambda p: p.stem)
def test_los_ejemplos_del_prompt_cumplen_el_contrato(ruta):
    """Un few-shot con un ejemplo inválido le enseñaría al modelo a romper el contrato."""
    ejemplos = re.findall(r"^JSON: (\{.*\})$", ruta.read_text(encoding="utf-8"), flags=re.MULTILINE)
    assert ejemplos, "El prompt no tiene ejemplos few-shot"
    for ejemplo in ejemplos:
        contrato_para(version_de(ruta))(**json.loads(ejemplo))
