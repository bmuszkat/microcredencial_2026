"""
Parte A de la Entrega 3: workflow encadenado con puntos de control (Clase 4, Hito 1).

Sigue el user journey B.2 de la Entrega 1 (design D3). Cada paso queda en la traza con su tipo:

    paso  qué hace                                              tipo    alcance
     0    anonimizar el DNI (el LLM nunca lo ve)                Regla   mensaje
     1    extraer intenciones y datos (prompt v3)               LLM     mensaje
     2    validar el contrato, reponer el DNI y su formato      Regla   mensaje
     3    enrutar cada intención                                Regla   mensaje
     4    ¿alguna intención necesita identificar al paciente?   Regla   mensaje
     5    identificar al paciente en el padrón                  Sensor  mensaje
     6-9  fechas, agenda, cargo y confirmación                  ...     intención   (tarea 6.2)
     10   redactar la respuesta                                 LLM     mensaje     (tarea 6.3)
     11   verificar horarios, fechas y montos del texto         Regla   mensaje     (tarea 6.3)

"La IA interpreta, la base de datos es la autoridad": el LLM solo extrae (paso 1) y redacta
(paso 10); todo lo que decide es código. El workflow NUNCA escribe en la agenda.
"""

import sys
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

ENTREGA_3 = Path(__file__).resolve().parent
# Se reusa clinica/ de la Entrega 2 sin moverlo (design D1).
sys.path.insert(0, str(ENTREGA_3.parent / "entrega_2"))
sys.path.insert(0, str(ENTREGA_3))

import herramientas  # noqa: E402
import reglas  # noqa: E402
from clinica.config import ConfiguracionError, detectar_proveedor, modelo_de  # noqa: E402
from clinica.extractor import ERRORES_DE_COMUNICACION, armar_mensaje_usuario, validar_respuesta  # noqa: E402
from clinica.llm import RespuestaNoJSON, llamar_con_reintentos, mensaje_del_error  # noqa: E402
from clinica.reglas import validar_dni  # noqa: E402
from reglas import COMPLETADO, DERIVADO, PENDIENTE, REVISION_HUMANA  # noqa: E402

PROMPT_EXTRACCION = "v3"
RUTA_PROMPT_EXTRACCION = ENTREGA_3 / "prompts" / f"extraccion_{PROMPT_EXTRACCION}.txt"

# Una función LLM recibe (system_prompt, mensaje_usuario) y devuelve el texto del modelo (design D13).
LLM = Callable[[str, str], str]

# Intenciones que operan sobre datos de una persona: sin identificarla no se resuelven (spec workflow-pedidos).
REQUIERE_IDENTIFICACION = {"crear_turno", "modificar_turno", "cancelar_turno", "consultar_resultado"}

REGLA, LLM_, SENSOR = "Regla", "LLM", "Sensor"


# ── Traza ─────────────────────────────────────────────────────────────────────

@dataclass
class PasoTraza:
    numero: int
    nombre: str
    tipo: str          # Regla, LLM o Sensor
    resultado: str
    ok: bool = True    # False: el flujo se detuvo (o la intención quedó frenada) en este paso


@dataclass
class Traza:
    pasos: list[PasoTraza] = field(default_factory=list)

    def registrar(self, numero: int, nombre: str, tipo: str, resultado: str, ok: bool = True) -> None:
        self.pasos.append(PasoTraza(numero, nombre, tipo, resultado, ok))

    def numeros(self) -> list[int]:
        return [p.numero for p in self.pasos]


# ── Contexto del mensaje ──────────────────────────────────────────────────────

@dataclass
class Contexto:
    """Lo que se sabe del mensaje a medida que avanza el workflow."""

    mensaje: str
    datos: dict                                   # backend (herramientas.cargar_datos)
    traza: Traza = field(default_factory=Traza)
    texto_para_llm: Optional[str] = None          # el mensaje anonimizado: lo único que sale hacia la API
    dni: Optional[str] = None                     # lo pone el código (paso 0), nunca el LLM
    extraccion: Optional[dict] = None
    paciente: Optional[dict] = None
    # Una entrada por intención: {"intencion", "estado" (None = todavía sin resolver), "motivo", ...datos}
    intenciones: list[dict] = field(default_factory=list)
    pendientes: list[dict] = field(default_factory=list)   # preguntas para el paciente (motivos de PENDIENTE)
    # Si un paso de mensaje detiene el flujo, define el estado de todo el mensaje.
    estado_detenido: Optional[str] = None
    paso_detenido: Optional[int] = None
    motivo_detenido: Optional[str] = None

    @property
    def detenido(self) -> bool:
        return self.estado_detenido is not None

    def detener(self, paso: int, estado: str, motivo: str) -> "Contexto":
        self.estado_detenido, self.paso_detenido, self.motivo_detenido = estado, paso, motivo
        return self


# ── LLM real ──────────────────────────────────────────────────────────────────

def llm_real() -> Optional[tuple[LLM, str]]:
    """(función LLM, descripción) con el proveedor del .env, o None si no hay key (modo simulación)."""
    proveedor = detectar_proveedor()
    if proveedor is None:
        return None
    nombre, key = proveedor
    return (lambda system, usuario: llamar_con_reintentos(system, usuario, nombre, key)), f"{nombre} ({modelo_de(nombre)})"


def _llamar(llm: LLM, system: str, usuario: str) -> tuple[Optional[str], Optional[str]]:
    """Llama al LLM y traduce cualquier falla a un motivo tipificado, sin romper el programa."""
    try:
        return llm(system, usuario), None
    except RespuestaNoJSON as e:
        return None, f"FORMATO: el proveedor rechazó la salida por no ser JSON ({e})"
    except urllib.error.HTTPError as e:
        return None, f"COMUNICACION: {mensaje_del_error(e)}"
    except (*ERRORES_DE_COMUNICACION, ConfiguracionError) as e:
        return None, f"COMUNICACION: {type(e).__name__}: {e}"


# ── Pasos de mensaje (0 a 5) ──────────────────────────────────────────────────

def paso_0_anonimizar(ctx: Contexto) -> Contexto:
    anonimo = reglas.anonimizar_dni(ctx.mensaje)
    ctx.texto_para_llm = anonimo.texto
    if anonimo.multiples:
        ctx.traza.registrar(0, "Anonimizar el DNI", REGLA,
                            f"{len(anonimo.candidatos)} números de documento distintos: no se elige ninguno", ok=False)
        ctx.pendientes.append({"motivo": "varios_dni"})
        return ctx.detener(0, PENDIENTE, "varios_dni")
    ctx.dni = anonimo.dni
    detalle = "DNI detectado y reemplazado por [DNI]" if anonimo.dni else "el mensaje no trae DNI"
    ctx.traza.registrar(0, "Anonimizar el DNI", REGLA, f"{detalle}. Se envía: \"{anonimo.texto}\"")
    return ctx


def paso_1_extraer(ctx: Contexto, llm: LLM) -> tuple[Contexto, Optional[str]]:
    system = RUTA_PROMPT_EXTRACCION.read_text(encoding="utf-8")
    texto, falla = _llamar(llm, system, armar_mensaje_usuario(ctx.texto_para_llm))
    if falla:
        ctx.traza.registrar(1, "Extraer intenciones y datos", LLM_, falla, ok=False)
        return ctx.detener(1, REVISION_HUMANA, falla), None
    ctx.traza.registrar(1, "Extraer intenciones y datos", LLM_, f"prompt {PROMPT_EXTRACCION}: {texto}")
    return ctx, texto


def paso_2_validar(ctx: Contexto, texto: str) -> Contexto:
    validacion = validar_respuesta(texto, PROMPT_EXTRACCION)
    if not validacion["ok"]:
        detalle = validacion["detalle"] if isinstance(validacion["detalle"], str) else "; ".join(validacion["detalle"])
        motivo = f"{validacion['error']}: {detalle}"
        ctx.traza.registrar(2, "Validar el contrato y el DNI", REGLA, motivo, ok=False)
        return ctx.detener(2, REVISION_HUMANA, motivo)

    extraccion = validacion["extraccion"]
    descartado = extraccion["dni"]
    extraccion["dni"] = ctx.dni  # el DNI lo pone el código: se descarta el que haya devuelto el LLM
    dni_ok, motivo_dni = validar_dni(ctx.dni)
    if not dni_ok:
        ctx.traza.registrar(2, "Validar el contrato y el DNI", REGLA, f"REGLA: {motivo_dni}", ok=False)
        return ctx.detener(2, REVISION_HUMANA, f"REGLA: {motivo_dni}")

    ctx.extraccion = extraccion
    nota = f" (se descartó el dni {descartado!r} del LLM)" if descartado is not None else ""
    ctx.traza.registrar(2, "Validar el contrato y el DNI", REGLA,
                        f"cumple el contrato; DNI repuesto por el código: {'sí' if ctx.dni else 'no hay'}{nota}")
    return ctx


def paso_3_enrutar(ctx: Contexto) -> Contexto:
    intenciones = ctx.extraccion["intenciones"]
    contradictorio = {"modificar_turno", "cancelar_turno"} <= set(intenciones)
    for intencion in intenciones:
        if intencion == "consulta_medica":
            ctx.intenciones.append({"intencion": intencion, "estado": DERIVADO, "motivo": "consulta_medica"})
        elif intencion == "otra":
            ctx.intenciones.append({"intencion": intencion, "estado": COMPLETADO, "motivo": "fuera_de_alcance"})
        elif contradictorio and intencion in ("modificar_turno", "cancelar_turno"):
            ctx.intenciones.append({"intencion": intencion, "estado": PENDIENTE, "motivo": "reprogramar_o_cancelar"})
        else:
            ctx.intenciones.append({"intencion": intencion, "estado": None})  # la resuelven los pasos 6 a 9
    if contradictorio:
        ctx.pendientes.append({"motivo": "reprogramar_o_cancelar"})
    ruta = ", ".join(f"{i['intencion']} → {i['estado'] or 'pasos 6-9'}" for i in ctx.intenciones)
    ctx.traza.registrar(3, "Enrutar cada intención", REGLA, ruta)
    return ctx


def paso_4_requiere_identificacion(ctx: Contexto) -> tuple[Contexto, bool]:
    necesitan = [i for i in ctx.intenciones if i["estado"] is None and i["intencion"] in REQUIERE_IDENTIFICACION]
    if not necesitan:
        ctx.traza.registrar(4, "¿Hace falta identificar al paciente?", REGLA, "no: ninguna intención lo requiere")
        return ctx, False
    nombres = ", ".join(i["intencion"] for i in necesitan)
    if ctx.dni is None:
        for i in necesitan:
            i.update(estado=PENDIENTE, motivo="falta_dni")
        ctx.pendientes.append({"motivo": "falta_dni"})
        ctx.traza.registrar(4, "¿Hace falta identificar al paciente?", REGLA,
                            f"sí ({nombres}) y el mensaje no trae DNI → se le pide", ok=False)
        return ctx.detener(4, PENDIENTE, "falta_dni"), True
    ctx.traza.registrar(4, "¿Hace falta identificar al paciente?", REGLA, f"sí ({nombres})")
    return ctx, True


def paso_5_identificar(ctx: Contexto) -> Contexto:
    paciente = herramientas.buscar_paciente(ctx.dni, ctx.datos)
    if paciente is None:
        for i in ctx.intenciones:
            if i["estado"] is None and i["intencion"] in REQUIERE_IDENTIFICACION:
                i.update(estado=REVISION_HUMANA, motivo="dni_no_registrado")
        ctx.traza.registrar(5, "Identificar al paciente en el padrón", SENSOR, "DNI no registrado en el padrón", ok=False)
        return ctx.detener(5, REVISION_HUMANA, "dni_no_registrado")
    ctx.paciente = paciente
    ctx.traza.registrar(5, "Identificar al paciente en el padrón", SENSOR, f"paciente identificado: {paciente['nombre']}")
    return ctx


def pasos_de_mensaje(mensaje: str, llm: LLM, datos: Optional[dict] = None) -> Contexto:
    """
    Pasos 0 a 5: se ejecutan una vez por mensaje. Si alguno falla, el contexto queda detenido
    con el estado de todo el mensaje; si no, queda listo para resolver cada intención (pasos 6 a 9).
    """
    ctx = Contexto(mensaje=mensaje, datos=datos if datos is not None else herramientas.cargar_datos())

    ctx = paso_0_anonimizar(ctx)
    if ctx.detenido:
        return ctx
    ctx, texto = paso_1_extraer(ctx, llm)
    if ctx.detenido:
        return ctx
    ctx = paso_2_validar(ctx, texto)
    if ctx.detenido:
        return ctx
    ctx = paso_3_enrutar(ctx)
    ctx, hace_falta = paso_4_requiere_identificacion(ctx)
    if ctx.detenido or not hace_falta:
        return ctx
    return paso_5_identificar(ctx)
