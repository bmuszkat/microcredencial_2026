"""
Reglas de negocio deterministas: si entra X, siempre sale Y.
Por eso las ejecuta Python y NO el LLM ("la IA interpreta, la base de datos es la autoridad").

Hoy (Entrega 2): formato del DNI — paso 3 del user journey de la Entrega 1.
Entrega 3: identidad contra el padrón (DNI + fecha de nacimiento), conversión de fechas
relativas a calendario, turno existente y política de reprogramación.
"""

import re
from typing import Optional

PATRON_DNI = re.compile(r"^\d{7,8}$")


def validar_dni(dni: Optional[str]) -> tuple[bool, str]:
    """
    El DNI argentino tiene 7 u 8 dígitos. El LLM lo entrega normalizado (solo dígitos);
    si viene con puntos, letras o largo incorrecto, la regla lo rechaza.
    Un DNI ausente (None) no es un error: el mensaje puede no traerlo.
    Devuelve (es_valido, motivo).
    """
    if dni is None:
        return True, "Sin DNI en el mensaje: no hay nada que validar"
    if not PATRON_DNI.match(dni):
        return False, f"DNI '{dni}' inválido: debe tener 7 u 8 dígitos, sin puntos ni letras"
    return True, "DNI con formato válido"
