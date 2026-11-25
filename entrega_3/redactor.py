"""
Respuesta al paciente: pasos 10 y 11 del workflow (spec `respuesta-paciente`, design D5, D10 y D11).

Quién escribe según el estado global (design D5):
    REVISION_HUMANA                        → acuse fijo (no revela el motivo interno)
    PENDIENTE                              → plantilla con las preguntas pendientes
    DERIVADO con solo consulta_medica      → plantilla de derivación
    COMPLETADO con solo `otra`             → plantilla de fuera de alcance
    COMPLETADO / PENDIENTE_CONFIRMACION /
    DERIVADO mixto                         → LLM redactor con los datos validados
                                             (si falla o no cumple el contrato → plantilla de respaldo)

El redactor NUNCA recibe el mensaje original del paciente: solo los datos validados.

Forma de los datos validados (la arma workflow.py):
    {
      "paciente": "Juan Pérez" | None,
      "intenciones": [
        {"intencion": "modificar_turno", "estado": "PENDIENTE_CONFIRMACION",
         "turno": {"profesional", "fecha" (ISO), "hora", "sede"},      # modificar / cancelar
         "opciones": [{"profesional", "fecha", "hora", "sede"}, ...],  # crear / modificar / disponibilidad
         "opciones_alternativas": bool,  # True: no había en lo pedido, son las más cercanas
         "cargo": 0 | 12000},                                          # modificar / cancelar
        {"intencion": "consultar_resultado", "estado": "COMPLETADO",
         "estudio": {"estudio", "estado", "entrega_estimada"}},
        {"intencion": "consulta_medica", "estado": "DERIVADO"},
        {"intencion": "otra", "estado": "COMPLETADO", "motivo": "fuera_de_alcance"},
      ],
      "pendientes": [{"motivo": "falta_dni"}, {"motivo": "sin_turnos_en_lo_pedido", "opciones": [...]}, ...]
    }
"""

import json
import urllib.error
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from clinica.extractor import ERRORES_DE_COMUNICACION
from clinica.llm import RespuestaNoJSON
from reglas import COMPLETADO, DERIVADO, PENDIENTE, PENDIENTE_CONFIRMACION, REVISION_HUMANA

PROMPT_REDACCION = Path(__file__).resolve().parent / "prompts" / "redaccion_v1.txt"

# Una función LLM recibe (system_prompt, mensaje_usuario) y devuelve el texto del modelo.
LLM = Callable[[str, str], str]

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


# ── Contrato de la salida del redactor ────────────────────────────────────────

class RespuestaRedactada(BaseModel):
    """Lo único que puede devolver el LLM redactor: una clave con texto no vacío."""

    model_config = ConfigDict(extra="forbid", strict=True)
    respuesta: str = Field(min_length=1, max_length=1200)


@dataclass
class Respuesta:
    """El texto que recibe el paciente y de dónde salió (para la traza)."""

    texto: str
    origen: str                         # "LLM" o "PLANTILLA"
    plantilla: Optional[str] = None     # acuse_revision, preguntas, derivacion, fuera_de_alcance, respaldo
    detalle: Optional[str] = None       # por qué se usó la plantilla de respaldo
    valores_sin_respaldo: list[str] = field(default_factory=list)  # lo que rechazó el guardrail (tarea 4.2)


# ── Formato de los datos ──────────────────────────────────────────────────────

def fecha_corta(iso: str) -> str:
    """'2026-11-27' → 'viernes 27/11' (el formato fijo que le pedimos al LLM)."""
    d = date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d.day:02d}/{d.month:02d}"


def monto(valor: int) -> str:
    """12000 → '$12.000'."""
    return "$" + f"{valor:,}".replace(",", ".")


def _turno(t: dict) -> str:
    return f"{fecha_corta(t['fecha'])} a las {t['hora']} con {t['profesional']} (sede {t['sede']})"


def _opciones(opciones: list[dict]) -> str:
    return "; ".join(_turno(t) for t in opciones)


ESTADO_ESTUDIO = {
    "listo": "está listo para retirar",
    "en_proceso": "ya se realizó y está en proceso de informe",
    "pendiente": "todavía no se realizó",
}


# ── Plantillas fijas (design D5) ──────────────────────────────────────────────
# Ninguna muestra turnos ni estudios registrados del paciente: con la identidad validada
# solo por DNI, eso le revelaría datos a cualquiera que conozca un DNI ajeno (design D4).

ACUSE_REVISION = ("¡Hola! Recibimos tu mensaje. Una persona del equipo de la clínica lo va a revisar "
                  "y te va a responder por este medio.")

DERIVACION = ("¡Hola! Las consultas médicas las responde un profesional de la clínica, no este asistente. "
              "Ya le pasamos tu mensaje y te va a contactar. Si tenés una urgencia, acercate a la guardia.")

FUERA_DE_ALCANCE = ("¡Hola! Por este medio podemos ayudarte a sacar, reprogramar o cancelar turnos y a consultar "
                    "si tus estudios están listos. Para otras consultas, comunicate con recepción.")

PREGUNTAS = {
    "falta_dni": "¿Me pasás tu número de DNI?",
    "varios_dni": "En tu mensaje aparece más de un número de documento. ¿Me confirmás cuál es tu DNI?",
    "reprogramar_o_cancelar": "¿Preferís reprogramar el turno o cancelarlo?",
    "fecha_no_entendida": "¿Qué día y en qué horario te queda bien?",
    "varios_turnos": "¿Qué día y a qué hora era el turno al que te referís?",
    "varios_estudios": "¿Por cuál de tus estudios consultás?",
    "sin_turnos_en_lo_pedido": "No hay turnos libres en el día y horario que pediste.",
}


def plantilla_preguntas(pendientes: list[dict]) -> str:
    lineas = []
    for p in pendientes:
        texto = PREGUNTAS[p["motivo"]]
        if p.get("opciones"):  # turnos LIBRES de la agenda: no son datos del paciente
            texto += f" Los más cercanos son: {_opciones(p['opciones'])}. ¿Te sirve alguno?"
        lineas.append(texto)
    return "¡Hola! Para seguir necesito un dato más. " + " ".join(dict.fromkeys(lineas))


def plantilla_respaldo(datos: dict) -> str:
    """La misma información que tendría la respuesta del LLM, armada con frases fijas."""
    partes = [f"¡Hola, {datos['paciente']}!" if datos.get("paciente") else "¡Hola!"]
    for i in datos["intenciones"]:
        intencion = i["intencion"]
        cargo = i.get("cargo", 0)
        aviso_cargo = (f" Como faltan menos de 24 horas, tiene un cargo de {monto(cargo)}." if cargo
                       else " No tiene cargo.")
        if intencion == "modificar_turno":
            partes.append(f"Para reprogramar tu turno del {_turno(i['turno'])} tenemos: "
                          f"{_opciones(i['opciones'])}.{aviso_cargo} ¿Cuál preferís?")
        elif intencion == "cancelar_turno":
            partes.append(f"¿Confirmás que querés cancelar tu turno del {_turno(i['turno'])}?{aviso_cargo}")
        elif intencion == "crear_turno":
            partes.append(f"Tenemos estos turnos libres: {_opciones(i['opciones'])}. ¿Cuál preferís?")
        elif intencion == "consultar_disponibilidad":
            intro = ("No hay turnos libres en lo que pediste; los más cercanos son"
                     if i.get("opciones_alternativas") else "Tenemos estos turnos libres")
            partes.append(f"{intro}: {_opciones(i['opciones'])}.")
        elif intencion == "consultar_resultado":
            e = i["estudio"]
            texto = f"Tu {e['estudio']} {ESTADO_ESTUDIO[e['estado']]}"
            if e["estado"] == "en_proceso" and e.get("entrega_estimada"):
                texto += f"; estaría listo el {fecha_corta(e['entrega_estimada'])}"
            partes.append(texto + ".")
        elif intencion == "consulta_medica":
            partes.append("Tu consulta médica se la pasamos a un profesional de la clínica, que te va a responder.")
    return " ".join(partes)


# ── Lo que ve el LLM redactor ─────────────────────────────────────────────────

QUE_HACER = {
    COMPLETADO: "informar",
    PENDIENTE_CONFIRMACION: "ofrecer_y_pedir_confirmacion",
    DERIVADO: "avisar_derivacion",
}

NOMBRE_PEDIDO = {
    "consultar_disponibilidad": "consultar turnos libres",
    "crear_turno": "sacar un turno nuevo",
    "modificar_turno": "reprogramar un turno",
    "cancelar_turno": "cancelar un turno",
    "consultar_resultado": "consultar un estudio",
    "consulta_medica": "consulta médica",
}


def vista_para_llm(datos: dict) -> dict:
    """Los datos validados con los valores ya formateados (dd/mm, HH:MM, $12.000), para que el LLM los copie."""
    def turno(t: dict) -> dict:
        return {"dia": fecha_corta(t["fecha"]), "hora": t["hora"], "profesional": t["profesional"], "sede": t["sede"]}

    pedidos = []
    for i in datos["intenciones"]:
        pedido = {"pedido": NOMBRE_PEDIDO[i["intencion"]], "que_hacer": QUE_HACER[i["estado"]]}
        if "turno" in i:
            pedido["turno_actual"] = turno(i["turno"])
        if "opciones" in i:
            pedido["opciones"] = [turno(t) for t in i["opciones"]]
            if i.get("opciones_alternativas"):
                pedido["nota"] = "no hay turnos libres en lo que pidió; estas son las opciones más cercanas"
        if "cargo" in i:
            pedido["cargo"] = monto(i["cargo"]) if i["cargo"] else "sin cargo"
        if "estudio" in i:
            e = i["estudio"]
            pedido["estudio"] = {"nombre": e["estudio"], "estado": ESTADO_ESTUDIO[e["estado"]]}
            if e["estado"] == "en_proceso" and e.get("entrega_estimada"):
                pedido["estudio"]["entrega_estimada"] = fecha_corta(e["entrega_estimada"])
        pedidos.append(pedido)
    return {"paciente": datos.get("paciente"), "pedidos": pedidos}


def redactar_con_llm(datos: dict, llm: LLM) -> tuple[Optional[str], Optional[str]]:
    """Llama al LLM con los datos validados. Devuelve (texto, None) o (None, motivo de la falla)."""
    usuario = "Datos validados (JSON):\n" + json.dumps(vista_para_llm(datos), ensure_ascii=False, indent=2)
    try:
        crudo = llm(PROMPT_REDACCION.read_text(encoding="utf-8"), usuario)
    except RespuestaNoJSON as e:
        return None, f"FORMATO: el proveedor rechazó la salida por no ser JSON ({e})"
    except urllib.error.HTTPError as e:
        return None, f"COMUNICACION: HTTP {e.code}"
    except ERRORES_DE_COMUNICACION as e:
        return None, f"COMUNICACION: {type(e).__name__}: {e}"
    try:
        return RespuestaRedactada(**json.loads(crudo or "")).respuesta, None
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"FORMATO: la redacción no es un objeto JSON ({e})"
    except ValidationError as e:
        return None, f"CONTRATO: la redacción no cumple el contrato ({e.error_count()} error/es)"


# ── Punto de entrada ──────────────────────────────────────────────────────────

def solo(datos: dict, intencion: str) -> bool:
    return [i["intencion"] for i in datos["intenciones"]] == [intencion]


def armar_respuesta(estado_global: str, datos: dict, llm: Optional[LLM]) -> Respuesta:
    """Elige quién escribe según el estado (design D5) y devuelve el texto para el paciente."""
    if estado_global == REVISION_HUMANA:
        return Respuesta(ACUSE_REVISION, "PLANTILLA", "acuse_revision")
    if estado_global == PENDIENTE:
        return Respuesta(plantilla_preguntas(datos["pendientes"]), "PLANTILLA", "preguntas")
    if estado_global == DERIVADO and solo(datos, "consulta_medica"):
        return Respuesta(DERIVACION, "PLANTILLA", "derivacion")
    if estado_global == COMPLETADO and solo(datos, "otra"):
        return Respuesta(FUERA_DE_ALCANCE, "PLANTILLA", "fuera_de_alcance")

    texto, falla = redactar_con_llm(datos, llm) if llm else (None, "sin LLM configurado")
    if texto is None:
        return Respuesta(plantilla_respaldo(datos), "PLANTILLA", "respaldo", detalle=falla)
    return Respuesta(texto, "LLM")
