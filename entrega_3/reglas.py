"""
Reglas del dominio del workflow (Entrega 3, Parte A): funciones puras y deterministas.

Si entra X, siempre sale Y. Por eso las ejecuta Python y no el LLM ("la IA interpreta,
la base de datos es la autoridad"). Cada regla corresponde a un paso [Regla] del journey B.2
de la Entrega 1 (ver design.md del cambio entrega-3-parte-a-workflow).
"""

import re
from dataclasses import dataclass
from typing import Optional

# ── Paso 0 · Anonimizar el DNI (design D6) ────────────────────────────────────

MARCADOR_DNI = "[DNI]"

# 7 u 8 dígitos, con o sin puntos de miles ("30.123.456", "30123456", "7.654.321").
# Los lookarounds evitan cortar un número más largo (un teléfono de 10 dígitos) y tomar
# un monto ("$1.200.000"), pero aceptan un punto final de oración ("DNI 30.123.456.").
PATRON_DNI = re.compile(
    r"(?<!\d)(?<!\d\.)(?<!\$)(?<!\$ )"
    r"\d{1,2}\.?\d{3}\.?\d{3}"
    r"(?!\d)(?!\.\d)"
)


@dataclass(frozen=True)
class Anonimizacion:
    """Resultado del paso 0: el texto que puede salir hacia la API y el DNI que se queda en el código."""

    texto: str                    # mensaje con cada DNI reemplazado por [DNI]
    dni: Optional[str]            # solo dígitos, si hubo exactamente un candidato
    candidatos: tuple[str, ...]   # todos los DNI distintos encontrados (normalizados)

    @property
    def multiples(self) -> bool:
        """Dos o más DNI distintos: el código no adivina cuál es el del paciente."""
        return len(self.candidatos) > 1


def anonimizar_dni(mensaje: str) -> Anonimizacion:
    """
    Detecta los DNI del mensaje, los reemplaza por [DNI] y devuelve el valor normalizado.
    - Ningún candidato → el texto queda igual y `dni` es None.
    - Un candidato (aunque aparezca repetido) → `dni` es ese valor.
    - Dos o más distintos → `dni` es None y `multiples` es True; igual se reemplazan todos,
      para que ningún DNI salga hacia la API.
    """
    candidatos: list[str] = []
    for encontrado in PATRON_DNI.findall(mensaje):
        normalizado = encontrado.replace(".", "")
        if normalizado not in candidatos:
            candidatos.append(normalizado)
    texto = PATRON_DNI.sub(MARCADOR_DNI, mensaje)
    dni = candidatos[0] if len(candidatos) == 1 else None
    return Anonimizacion(texto=texto, dni=dni, candidatos=tuple(candidatos))
