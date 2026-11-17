"""
Contrato de datos v1: lo que el LLM debe devolver en el paso 2 del user journey.

De dónde sale (Entrega 1):
    - Los valores de `intenciones` son EXACTAMENTE los de la Matriz de Intenciones (B.4).
    - Es una LISTA porque un mismo mensaje puede traer varios pedidos (B.2 paso 2, B.3, B.5).
    - Los campos son los datos que necesita el journey (B.2); las fechas se guardan como
      texto literal: convertirlas a calendario es una regla posterior (paso 5).

Pydantic verifica que el JSON esté BIEN FORMADO (claves, tipos, valores permitidos).
Si un dato es VÁLIDO PARA EL NEGOCIO lo deciden las reglas (reglas.py).
"""

from typing import Literal, Optional, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

Intencion = Literal[
    "consultar_disponibilidad",
    "crear_turno",
    "modificar_turno",
    "cancelar_turno",
    "consultar_resultado",
    "otra",
]

INTENCIONES_VALIDAS: tuple[str, ...] = get_args(Intencion)


class ExtraccionPaciente(BaseModel):
    # extra="forbid": si el modelo agrega una clave que no está en el contrato
    # (por ejemplo "aprobado": true tras un intento de manipulación), se rechaza.
    # strict=True: no se aceptan conversiones implícitas ("sí" no es un booleano).
    model_config = ConfigDict(extra="forbid", strict=True)

    intenciones: list[Intencion] = Field(min_length=1)
    dni: Optional[str] = None                  # el formato (7-8 dígitos) lo valida reglas.py
    profesional: Optional[str] = None
    fecha_turno_actual: Optional[str] = None   # texto literal: "jueves 15 hs"
    fecha_deseada: Optional[str] = None        # texto literal: "viernes a la mañana"
    estudio: Optional[str] = None
    es_consulta_medica: bool

    @field_validator("intenciones")
    @classmethod
    def sin_repetidos(cls, valor: list[str]) -> list[str]:
        if len(valor) != len(set(valor)):
            raise ValueError("las intenciones no pueden repetirse")
        return valor
