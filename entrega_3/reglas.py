"""
Reglas del dominio del workflow (Entrega 3, Parte A): funciones puras y deterministas.

Si entra X, siempre sale Y. Por eso las ejecuta Python y no el LLM ("la IA interpreta,
la base de datos es la autoridad"). Cada regla corresponde a un paso [Regla] del journey B.2
de la Entrega 1 (ver design.md del cambio entrega-3-parte-a-workflow).
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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


# ── Paso 6 · Convertir fechas relativas (design D7) ───────────────────────────

FRANJA_MANANA = ("08:00", "13:00")
FRANJA_TARDE = ("13:00", "19:00")

DIAS_SEMANA = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}

_FRANJAS = [
    (re.compile(r"\b(?:a|por|de) la manana\b|\bde manana\b"), FRANJA_MANANA),
    (re.compile(r"\b(?:a|por|de) la tarde\b|\bde tarde\b"), FRANJA_TARDE),
]
_SEMANA_QUE_VIENE = re.compile(r"\b(?:la )?(?:semana que viene|proxima semana|semana proxima)\b")
_DIA_MES = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/\d{2,4})?(?![\d/])")
# "15 hs", "15hs", "15 h", "9:30", "9.30", "a las 9", "a las 9:30 hs"
_HORA = re.compile(r"\ba las (\d{1,2})(?:[:.](\d{2}))?\b|\b(\d{1,2})(?:[:.](\d{2}))?\s*(?:hs|h|horas)\b|\b(\d{1,2})[:.](\d{2})\b")
_TARDE_O_NOCHE = re.compile(r"\bde la (?:tarde|noche)\b")


@dataclass(frozen=True)
class FechaConvertida:
    """Una fecha literal convertida a calendario: un rango de días y, opcionalmente, una franja o una hora exacta."""

    desde: date
    hasta: date
    franja: Optional[tuple[str, str]] = None   # ("08:00", "13:00"), [inicio, fin)
    hora: Optional[str] = None                 # "15:00" si el paciente dio una hora exacta

    @property
    def un_solo_dia(self) -> bool:
        return self.desde == self.hasta


def _normalizar_fecha(texto: str) -> str:
    """Minúsculas y sin tildes, conservando '/', ':' y '.' (los necesitan las fechas y las horas)."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(sin_tildes.replace(",", " ").split())


def _hora_explicita(texto: str) -> tuple[Optional[str], bool]:
    """
    Devuelve (hora "HH:MM" o None, es_valida). "a las 3 de la tarde" → 15:00.
    Una hora imposible ("25 hs") hace que toda la fecha se considere no entendida.
    """
    encontrada = _HORA.search(texto)
    if not encontrada:
        return None, True
    grupos = encontrada.groups()
    horas_txt, minutos_txt = next((grupos[i], grupos[i + 1]) for i in (0, 2, 4) if grupos[i] is not None)
    horas, minutos = int(horas_txt), int(minutos_txt or 0)
    if horas < 12 and _TARDE_O_NOCHE.search(texto):
        horas += 12
    if not (0 <= horas <= 23 and 0 <= minutos <= 59):
        return None, False
    return f"{horas:02d}:{minutos:02d}", True


def _proximo(dia_semana: int, desde: date) -> date:
    """La próxima fecha con ese día de la semana, desde `desde` inclusive."""
    return desde + timedelta(days=(dia_semana - desde.weekday()) % 7)


def convertir_fecha(texto: Optional[str], referencia: datetime) -> Optional[FechaConvertida]:
    """
    Convierte una fecha literal extraída por el LLM ("viernes a la mañana", "jueves 15 hs",
    "la semana que viene", "27/11") en fechas de calendario, tomando `referencia` como "ahora".
    Devuelve None si no se entiende: el workflow nunca adivina una fecha (queda PENDIENTE).
    """
    if not texto or not texto.strip():
        return None
    t = _normalizar_fecha(texto)
    hoy = referencia.date()

    hora, hora_valida = _hora_explicita(t)
    if not hora_valida:
        return None

    # Franja: se busca y se saca del texto, para que "a la mañana" no se lea como "mañana" (el día siguiente).
    franja = None
    for patron, rango in _FRANJAS:
        if patron.search(t):
            franja = rango
            t = patron.sub(" ", t)
    if hora:
        franja = None  # una hora exacta es más precisa que la franja

    palabras = t.split()
    dias_nombrados = {DIAS_SEMANA[p] for p in palabras if p in DIAS_SEMANA}
    if len(dias_nombrados) > 1:
        return None  # "lunes o martes": no se elige por el paciente
    dia_semana = next(iter(dias_nombrados), None)

    desde = hasta = None
    dia_mes = _DIA_MES.search(t)
    if dia_mes:
        try:
            desde = hasta = date(hoy.year, int(dia_mes.group(2)), int(dia_mes.group(1)))
        except ValueError:
            return None  # "31/02"
        if dia_semana is not None and desde.weekday() != dia_semana:
            return None  # "jueves 27/11" pero el 27/11 es viernes: contradictorio
    elif _SEMANA_QUE_VIENE.search(t):
        lunes = hoy + timedelta(days=7 - hoy.weekday())
        if dia_semana is not None:      # "el miércoles de la semana que viene"
            desde = hasta = lunes + timedelta(days=dia_semana)
        else:                           # toda la semana hábil siguiente
            desde, hasta = lunes, lunes + timedelta(days=4)
    elif dia_semana is not None:
        desde = hasta = _proximo(dia_semana, hoy)
    elif re.search(r"\bpasado manana\b", t):
        desde = hasta = hoy + timedelta(days=2)
    elif "manana" in palabras:
        desde = hasta = hoy + timedelta(days=1)
    elif "hoy" in palabras:
        desde = hasta = hoy

    if desde is None:
        return None  # "cuando pueda", "a la mañana" sola, "a las 9" sin día
    return FechaConvertida(desde=desde, hasta=hasta, franja=franja, hora=hora)
