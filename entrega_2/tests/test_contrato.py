"""Pruebas del contrato de extracción (spec `extraccion-mensajes`). No usan la API."""

import pytest
from pydantic import ValidationError

from clinica.contrato import INTENCIONES_VALIDAS, ExtraccionPaciente

VALIDA = {
    "intenciones": ["modificar_turno", "consultar_resultado"],
    "dni": "30123456",
    "profesional": "Dra. López",
    "fecha_turno_actual": "jueves 15 hs",
    "fecha_deseada": "viernes a la mañana",
    "estudio": "campo visual",
    "es_consulta_medica": False,
}


def con(**cambios):
    return {**VALIDA, **cambios}


def test_las_intenciones_son_exactamente_las_de_la_matriz_de_la_entrega_1():
    assert set(INTENCIONES_VALIDAS) == {
        "consultar_disponibilidad", "crear_turno", "modificar_turno",
        "cancelar_turno", "consultar_resultado", "otra",
    }


def test_extraccion_completa_con_dos_intenciones_es_valida():
    extraccion = ExtraccionPaciente(**VALIDA)
    assert extraccion.intenciones == ["modificar_turno", "consultar_resultado"]


def test_entidades_en_null_son_validas():
    extraccion = ExtraccionPaciente(intenciones=["otra"], es_consulta_medica=True)
    assert extraccion.dni is None and extraccion.fecha_deseada is None


@pytest.mark.parametrize("datos, campo", [
    (con(intenciones=["aprobar_turno_urgente"]), "intenciones"),   # intención inventada
    (con(intenciones=[]), "intenciones"),                          # lista vacía
    (con(intenciones=["otra", "otra"]), "intenciones"),            # repetida
    (con(intenciones="modificar_turno"), "intenciones"),           # string en vez de lista
    (con(es_consulta_medica="sí"), "es_consulta_medica"),          # no es booleano
    (con(dni=30123456), "dni"),                                    # número en vez de string
    ({k: v for k, v in VALIDA.items() if k != "intenciones"}, "intenciones"),  # falta la clave
])
def test_contrato_rechaza_datos_mal_formados(datos, campo):
    with pytest.raises(ValidationError) as error:
        ExtraccionPaciente(**datos)
    assert campo in str(error.value)


def test_contrato_rechaza_campos_extra_como_aprobaciones():
    """Defensa estructural contra manipulación: no existe ningún campo para aprobar o ejecutar."""
    with pytest.raises(ValidationError, match="aprobado"):
        ExtraccionPaciente(**con(aprobado=True))
