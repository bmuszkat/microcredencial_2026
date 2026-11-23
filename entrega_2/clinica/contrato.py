"""
Contratos de datos: lo que el LLM debe devolver en el paso 2 del user journey.

De dónde sale (Entrega 1):
    - Los valores de `intenciones` son EXACTAMENTE los de la Matriz de Intenciones (B.4).
    - Es una LISTA porque un mismo mensaje puede traer varios pedidos (B.2 paso 2, B.3, B.5).
    - Las fechas se guardan como texto literal: convertirlas a calendario es una regla
      posterior (paso 5).

Hay un contrato por versión de prompt, para que una versión anterior siga siendo
reproducible cuando el contrato evoluciona:
    - v1 (y zeroshot, que es el v1 sin ejemplos): la consulta médica es `otra` + el flag
      `es_consulta_medica`.
    - v2 (vigente): la consulta médica tiene intención propia (`consulta_medica`), no hay
      flag, y `otra` queda solo para lo que está fuera de alcance o no se entiende.

Pydantic verifica que el JSON esté BIEN FORMADO (claves, tipos, valores permitidos).
Si un dato es VÁLIDO PARA EL NEGOCIO lo deciden las reglas (reglas.py).
"""

from typing import Literal, Optional, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── v2 (vigente) ──────────────────────────────────────────────────────────────

Intencion = Literal[
    "consultar_disponibilidad",
    "crear_turno",
    "modificar_turno",
    "cancelar_turno",
    "consultar_resultado",
    "consulta_medica",
    "otra",
]

INTENCIONES_VALIDAS: tuple[str, ...] = get_args(Intencion)


def _sin_repetidos(valor: list[str]) -> list[str]:
    if len(valor) != len(set(valor)):
        raise ValueError("las intenciones no pueden repetirse")
    return valor


class ExtraccionPaciente(BaseModel):
    """Contrato v2 (vigente)."""

    # extra="forbid": si el modelo agrega una clave que no está en el contrato
    # (por ejemplo "aprobado": true tras un intento de manipulación), se rechaza.
    # strict=True: no se aceptan conversiones implícitas (30123456 no es un string).
    model_config = ConfigDict(extra="forbid", strict=True)

    intenciones: list[Intencion] = Field(min_length=1)
    dni: Optional[str] = None                  # el formato (7-8 dígitos) lo valida reglas.py
    profesional: Optional[str] = None
    fecha_turno_actual: Optional[str] = None   # texto literal: "jueves 15 hs"
    fecha_deseada: Optional[str] = None        # texto literal: "viernes a la mañana"
    estudio: Optional[str] = None

    @field_validator("intenciones")
    @classmethod
    def validar_intenciones(cls, valor: list[str]) -> list[str]:
        valor = _sin_repetidos(valor)
        # "otra" significa "no hay ningún pedido que el sistema atienda": no se combina.
        if "otra" in valor and len(valor) > 1:
            raise ValueError("'otra' no se combina con otras intenciones")
        return valor


# ── v1 (registro: la versión documentada en la primera corrida) ────────────────

IntencionV1 = Literal[
    "consultar_disponibilidad",
    "crear_turno",
    "modificar_turno",
    "cancelar_turno",
    "consultar_resultado",
    "otra",
]

INTENCIONES_V1: tuple[str, ...] = get_args(IntencionV1)


class ExtraccionPacienteV1(BaseModel):
    """Contrato v1: la consulta médica se marca con `es_consulta_medica`."""

    model_config = ConfigDict(extra="forbid", strict=True)

    intenciones: list[IntencionV1] = Field(min_length=1)
    dni: Optional[str] = None
    profesional: Optional[str] = None
    fecha_turno_actual: Optional[str] = None
    fecha_deseada: Optional[str] = None
    estudio: Optional[str] = None
    es_consulta_medica: bool

    @field_validator("intenciones")
    @classmethod
    def sin_repetidos(cls, valor: list[str]) -> list[str]:
        return _sin_repetidos(valor)


# ── Qué contrato usa cada versión de prompt ────────────────────────────────────

CONTRATOS: dict[str, type[BaseModel]] = {
    "v1": ExtraccionPacienteV1,
    "zeroshot": ExtraccionPacienteV1,   # es el v1 sin ejemplos
    "v2": ExtraccionPaciente,
}


def contrato_para(version: str) -> type[BaseModel]:
    """Contrato de la versión de prompt; una versión nueva sin registrar usa el más reciente."""
    return CONTRATOS.get(version, ExtraccionPaciente)
