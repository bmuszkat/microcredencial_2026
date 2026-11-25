"""
Sensores: consultas de SOLO LECTURA sobre el backend ficticio de la clínica (spec `agenda-clinica`).

Es la "autoridad" del patrón "la IA interpreta, la base de datos es la autoridad": el LLM nunca
decide si un paciente existe, si un turno está en la agenda o si un estudio está listo; lo
responden estas funciones con los datos de `datos/`. El workflow (Parte A) las usa en los
pasos 5 y 7, y el agente (Parte C) las va a envolver como herramientas.

Ninguna función modifica los datos: todas devuelven copias.
"""

import copy
import json
import unicodedata
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

DIRECTORIO_DATOS = Path(__file__).resolve().parent / "datos"


# ── Carga de los datos ────────────────────────────────────────────────────────

def cargar_datos(directorio: Path = DIRECTORIO_DATOS) -> dict:
    """Lee los cuatro archivos del backend y los devuelve juntos."""
    def leer(nombre: str) -> dict:
        return json.loads((directorio / nombre).read_text(encoding="utf-8"))

    agenda = leer("agenda.json")
    return {
        "fecha_referencia": agenda["fecha_referencia"],
        "pacientes": leer("padron.json")["pacientes"],
        "profesionales": agenda["profesionales"],
        "turnos_reservados": agenda["turnos_reservados"],
        "turnos_libres": agenda["turnos_libres"],
        "estudios": leer("estudios.json")["estudios"],
        "politica_cargos": leer("politica_cargos.json"),
    }


@lru_cache(maxsize=1)
def _datos_por_defecto() -> dict:
    return cargar_datos()


def _datos(datos: Optional[dict]) -> dict:
    return datos if datos is not None else _datos_por_defecto()


# ── Comparación de textos ─────────────────────────────────────────────────────

def normalizar(texto: Optional[str]) -> str:
    """Minúsculas, sin tildes, sin puntuación y con espacios simples: 'Dra. López' → 'dra lopez'."""
    if not texto:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
    limpio = "".join(c if c.isalnum() else " " for c in sin_tildes)
    return " ".join(limpio.split())


def _contiene_palabras(texto: str, buscado: str) -> bool:
    """True si las palabras de `buscado` aparecen seguidas y completas en `texto` ('oct' no está en 'doctor')."""
    palabras, partes = texto.split(), buscado.split()
    if not partes:
        return False
    return any(palabras[i:i + len(partes)] == partes for i in range(len(palabras) - len(partes) + 1))


def coincide_profesional(mencionado: Optional[str], registrado: str) -> bool:
    """
    Compara por apellido: 'la doctora Lopez', 'López' y 'Dra. López' coinciden con 'Dra. López'.
    Sin profesional mencionado no hay filtro (coincide con todos).
    """
    if not mencionado or not normalizar(mencionado):
        return True
    return normalizar(mencionado).split()[-1] == normalizar(registrado).split()[-1]


# ── Consultas ─────────────────────────────────────────────────────────────────

def ahora(datos: Optional[dict] = None) -> datetime:
    """La fecha y hora de referencia del sistema ("ahora"), no la del reloj: así los resultados son reproducibles."""
    return datetime.fromisoformat(_datos(datos)["fecha_referencia"])


def buscar_paciente(dni: Optional[str], datos: Optional[dict] = None) -> Optional[dict]:
    """El paciente con ese DNI, o None si no está en el padrón."""
    if not dni:
        return None
    encontrado = next((p for p in _datos(datos)["pacientes"] if p["dni"] == dni), None)
    return copy.deepcopy(encontrado)


def _momento(turno: dict) -> datetime:
    return datetime.fromisoformat(f"{turno['fecha']}T{turno['hora']}")


def turnos_futuros(dni: str, datos: Optional[dict] = None) -> list[dict]:
    """Turnos reservados del paciente posteriores a la fecha de referencia, ordenados por fecha y hora."""
    d = _datos(datos)
    referencia = ahora(d)
    futuros = [t for t in d["turnos_reservados"] if t["dni"] == dni and _momento(t) > referencia]
    return copy.deepcopy(sorted(futuros, key=_momento))


def buscar_estudios(dni: str, nombre: Optional[str] = None, datos: Optional[dict] = None) -> list[dict]:
    """
    Estudios del paciente cuyo nombre coincide con `nombre`, sin distinguir mayúsculas ni tildes
    ('el campo visual' encuentra 'campo visual'). Sin nombre, devuelve todos los del paciente.
    Quien llama decide qué hacer si hay cero, uno o varios.
    """
    del_paciente = [e for e in _datos(datos)["estudios"] if e["dni"] == dni]
    if nombre:
        buscado = normalizar(nombre)
        del_paciente = [e for e in del_paciente
                        if _contiene_palabras(buscado, normalizar(e["estudio"]))
                        or _contiene_palabras(normalizar(e["estudio"]), buscado)]
    return copy.deepcopy(del_paciente)


def turnos_libres(desde: date, hasta: date, franja: Optional[tuple[str, str]] = None,
                  profesional: Optional[str] = None, datos: Optional[dict] = None) -> list[dict]:
    """
    Turnos libres entre `desde` y `hasta` (inclusive), dentro de la franja horaria [inicio, fin)
    en formato "HH:MM" si se indica, y del profesional si se indica (por apellido).
    Ordenados por fecha y hora. Solo devuelve turnos posteriores a la fecha de referencia.
    """
    d = _datos(datos)
    referencia = ahora(d)
    resultado = [
        t for t in d["turnos_libres"]
        if desde.isoformat() <= t["fecha"] <= hasta.isoformat()
        and (franja is None or franja[0] <= t["hora"] < franja[1])
        and coincide_profesional(profesional, t["profesional"])
        and _momento(t) > referencia
    ]
    return copy.deepcopy(sorted(resultado, key=lambda t: (_momento(t), t["profesional"])))


def datos_profesional(nombre: str, datos: Optional[dict] = None) -> Optional[dict]:
    """Especialidad y sede del profesional registrado con ese nombre (o que coincide por apellido)."""
    encontrado = next((p for p in _datos(datos)["profesionales"] if coincide_profesional(nombre, p["nombre"])), None)
    return copy.deepcopy(encontrado)


def politica_cargos(datos: Optional[dict] = None) -> dict:
    """Umbral de horas, monto y a qué intenciones aplica el cargo por reprogramar o cancelar."""
    return copy.deepcopy(_datos(datos)["politica_cargos"])
