"""Pruebas de los contratos de extracción (spec `extraccion-mensajes`). No usan la API."""

import pytest
from pydantic import ValidationError

from clinica.contrato import (
    CONTRATOS,
    INTENCIONES_V1,
    INTENCIONES_VALIDAS,
    ExtraccionPaciente,
    ExtraccionPacienteV1,
    contrato_para,
)

# ══ Contrato v2 (vigente) ══════════════════════════════════════════════════════

VALIDA = {
    "intenciones": ["modificar_turno", "consultar_resultado"],
    "dni": "30123456",
    "profesional": "Dra. López",
    "fecha_turno_actual": "jueves 15 hs",
    "fecha_deseada": "viernes a la mañana",
    "estudio": "campo visual",
}


def con(**cambios):
    return {**VALIDA, **cambios}


def test_las_intenciones_son_exactamente_las_de_la_matriz_vigente():
    assert set(INTENCIONES_VALIDAS) == {
        "consultar_disponibilidad", "crear_turno", "modificar_turno",
        "cancelar_turno", "consultar_resultado", "consulta_medica", "otra",
    }


def test_extraccion_completa_con_dos_intenciones_es_valida():
    extraccion = ExtraccionPaciente(**VALIDA)
    assert extraccion.intenciones == ["modificar_turno", "consultar_resultado"]


def test_consulta_medica_sola_es_valida():
    assert ExtraccionPaciente(intenciones=["consulta_medica"]).intenciones == ["consulta_medica"]


def test_consulta_medica_combinada_con_un_turno_es_valida():
    extraccion = ExtraccionPaciente(intenciones=["crear_turno", "consulta_medica"], profesional="Dra. Paz")
    assert set(extraccion.intenciones) == {"crear_turno", "consulta_medica"}


def test_entidades_en_null_son_validas():
    extraccion = ExtraccionPaciente(intenciones=["otra"])
    assert extraccion.dni is None and extraccion.fecha_deseada is None


@pytest.mark.parametrize("datos, campo", [
    (con(intenciones=["aprobar_turno_urgente"]), "intenciones"),   # intención inventada
    (con(intenciones=[]), "intenciones"),                          # lista vacía
    (con(intenciones=["otra", "otra"]), "intenciones"),            # repetida
    (con(intenciones=["crear_turno", "otra"]), "intenciones"),     # otra combinada
    (con(intenciones="modificar_turno"), "intenciones"),           # string en vez de lista
    (con(dni=30123456), "dni"),                                    # número en vez de string
    (con(es_consulta_medica=True), "es_consulta_medica"),          # el flag del v1 ya no existe
    ({k: v for k, v in VALIDA.items() if k != "intenciones"}, "intenciones"),  # falta la clave
])
def test_contrato_rechaza_datos_mal_formados(datos, campo):
    with pytest.raises(ValidationError) as error:
        ExtraccionPaciente(**datos)
    assert campo in str(error.value)


def test_otra_combinada_explica_el_motivo():
    with pytest.raises(ValidationError, match="no se combina"):
        ExtraccionPaciente(intenciones=["crear_turno", "otra"])


def test_contrato_rechaza_campos_extra_como_aprobaciones():
    """Defensa estructural contra manipulación: no existe ningún campo para aprobar o ejecutar."""
    with pytest.raises(ValidationError, match="aprobado"):
        ExtraccionPaciente(**con(aprobado=True))


# ══ Contrato v1 (registro: tiene que seguir validando las respuestas del prompt v1) ══

VALIDA_V1 = {**VALIDA, "es_consulta_medica": False}


def test_intenciones_v1_sin_consulta_medica():
    assert "consulta_medica" not in INTENCIONES_V1
    assert set(INTENCIONES_V1) == set(INTENCIONES_VALIDAS) - {"consulta_medica"}


def test_v1_acepta_su_formato_con_el_flag():
    extraccion = ExtraccionPacienteV1(intenciones=["otra"], es_consulta_medica=True)
    assert extraccion.es_consulta_medica is True


@pytest.mark.parametrize("datos, campo", [
    ({**VALIDA_V1, "intenciones": ["consulta_medica"]}, "intenciones"),  # no existía en v1
    ({**VALIDA_V1, "es_consulta_medica": "sí"}, "es_consulta_medica"),   # no es booleano
    ({k: v for k, v in VALIDA_V1.items() if k != "es_consulta_medica"}, "es_consulta_medica"),
])
def test_v1_rechaza_datos_mal_formados(datos, campo):
    with pytest.raises(ValidationError) as error:
        ExtraccionPacienteV1(**datos)
    assert campo in str(error.value)


# ══ Registro por versión ══════════════════════════════════════════════════════

@pytest.mark.parametrize("version, contrato", [
    ("v1", ExtraccionPacienteV1),
    ("zeroshot", ExtraccionPacienteV1),
    ("v2", ExtraccionPaciente),
    ("v3", ExtraccionPaciente),   # una versión nueva sin registrar usa el más reciente
])
def test_contrato_para_cada_version(version, contrato):
    assert contrato_para(version) is contrato


def test_todas_las_versiones_registradas_tienen_prompt():
    from clinica.config import RAIZ_ENTREGA
    for version in CONTRATOS:
        assert (RAIZ_ENTREGA / "prompts" / f"extraccion_{version}.txt").exists() or version == "v2"
