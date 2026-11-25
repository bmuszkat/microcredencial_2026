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
     6    convertir fechas relativas                            Regla   intención
     7    verificar turno, estudio y disponibilidad             Sensor  intención
     8    cargo por reprogramar o cancelar con < 24 h           Regla   intención
     9    si la operación escribe → PENDIENTE_CONFIRMACION      Regla   intención
     10   redactar la respuesta (o plantilla, según el estado)  LLM     mensaje
     11   verificar horarios, fechas y montos del texto         Regla   mensaje

"La IA interpreta, la base de datos es la autoridad": el LLM solo extrae (paso 1) y redacta
(paso 10); todo lo que decide es código. El workflow NUNCA escribe en la agenda.
"""

import sys
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

ENTREGA_3 = Path(__file__).resolve().parent
# Se reusa clinica/ de la Entrega 2 sin moverlo (design D1).
sys.path.insert(0, str(ENTREGA_3.parent / "entrega_2"))
sys.path.insert(0, str(ENTREGA_3))

import herramientas  # noqa: E402
import redactor  # noqa: E402
import reglas  # noqa: E402
from clinica.config import ConfiguracionError, detectar_proveedor, modelo_de  # noqa: E402
from clinica.extractor import ERRORES_DE_COMUNICACION, armar_mensaje_usuario, validar_respuesta  # noqa: E402
from clinica.llm import RespuestaNoJSON, llamar_con_reintentos, mensaje_del_error  # noqa: E402
from clinica.reglas import validar_dni  # noqa: E402
from reglas import (COMPLETADO, DERIVADO, PENDIENTE, PENDIENTE_CONFIRMACION, REVISION_HUMANA,  # noqa: E402
                    FechaConvertida)

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


# ── Pasos por intención (6 a 9) ───────────────────────────────────────────────

MAX_OPCIONES = 3              # turnos libres que se ofrecen (design D9)
HORIZONTE_DIAS = 30           # hasta dónde se buscan turnos libres cuando no hay fecha o como alternativa


def _con_sede(turno: dict, datos: dict) -> dict:
    """El turno en la forma que usa el redactor: profesional, fecha ISO, hora y sede."""
    profesional = herramientas.datos_profesional(turno["profesional"], datos) or {}
    return {"profesional": turno["profesional"], "fecha": turno["fecha"], "hora": turno["hora"],
            "sede": profesional.get("sede", "a confirmar")}


def _describir(t: dict) -> str:
    return f"{t['fecha']} {t['hora']} {t['profesional']}"


def _convertir(ctx: Contexto, intencion: dict, texto: Optional[str], campo: str) -> tuple[Optional[FechaConvertida], bool]:
    """
    Paso 6 · Regla. Devuelve (fecha convertida o None, se_entendio).
    Una fecha ausente no es un error (se_entendio=True con None); una que no se entiende, sí.
    """
    nombre = f"Convertir fechas ({intencion['intencion']})"
    if not texto:
        ctx.traza.registrar(6, nombre, REGLA, f"{campo}: no la indicó")
        return None, True
    fecha = reglas.convertir_fecha(texto, herramientas.ahora(ctx.datos))
    if fecha is None:
        ctx.traza.registrar(6, nombre, REGLA, f"{campo}: '{texto}' no se entiende → se le pregunta", ok=False)
        return None, False
    rango = fecha.desde.isoformat() if fecha.un_solo_dia else f"{fecha.desde.isoformat()} a {fecha.hasta.isoformat()}"
    if fecha.hora:
        rango += f", {fecha.hora}"
    elif fecha.franja:
        rango += f", {fecha.franja[0]}-{fecha.franja[1]}"
    ctx.traza.registrar(6, nombre, REGLA, f"{campo}: '{texto}' → {rango}")
    return fecha, True


def _buscar_libres(ctx: Contexto, fecha: Optional[FechaConvertida], profesional: Optional[str]) -> list[dict]:
    """Turnos libres en lo pedido (o los próximos, si no indicó fecha)."""
    ahora = herramientas.ahora(ctx.datos)
    if fecha is None:
        return herramientas.turnos_libres(ahora.date(), ahora.date() + timedelta(days=HORIZONTE_DIAS),
                                          None, profesional, ctx.datos)
    libres = herramientas.turnos_libres(fecha.desde, fecha.hasta, fecha.franja, profesional, ctx.datos)
    return [t for t in libres if t["hora"] == fecha.hora] if fecha.hora else libres


def _alternativas(ctx: Contexto, fecha: Optional[FechaConvertida], profesional: Optional[str]) -> list[dict]:
    """Los turnos libres más cercanos a lo pedido, cuando en lo pedido no hay ninguno."""
    ahora = herramientas.ahora(ctx.datos)
    desde = max(fecha.desde, ahora.date()) if fecha else ahora.date()
    return herramientas.turnos_libres(desde, desde + timedelta(days=HORIZONTE_DIAS), None, profesional, ctx.datos)


def _ofrecer(ctx: Contexto, intencion: dict, fecha: Optional[FechaConvertida], profesional: Optional[str],
             estado_si_hay: str) -> None:
    """
    Paso 7 (disponibilidad) · Sensor. Si hay turnos libres en lo pedido, la intención queda en
    `estado_si_hay` con hasta 3 opciones. Si no hay, se buscan alternativas (design D9).
    """
    nombre = f"Verificar disponibilidad ({intencion['intencion']})"
    libres = _buscar_libres(ctx, fecha, profesional)[:MAX_OPCIONES]
    if libres:
        intencion.update(estado=estado_si_hay, opciones=[_con_sede(t, ctx.datos) for t in libres],
                         opciones_alternativas=False)
        ctx.traza.registrar(7, nombre, SENSOR, "turnos libres: " + "; ".join(_describir(t) for t in libres))
        return
    alternativas = [_con_sede(t, ctx.datos) for t in _alternativas(ctx, fecha, profesional)[:MAX_OPCIONES]]
    if intencion["intencion"] == "consultar_disponibilidad" and alternativas:
        intencion.update(estado=COMPLETADO, opciones=alternativas, opciones_alternativas=True)
        ctx.traza.registrar(7, nombre, SENSOR, "sin turnos libres en lo pedido; se informan los más cercanos")
        return
    intencion.update(estado=PENDIENTE, motivo="sin_turnos_en_lo_pedido")
    ctx.pendientes.append({"motivo": "sin_turnos_en_lo_pedido", "opciones": alternativas})
    ctx.traza.registrar(7, nombre, SENSOR, "sin turnos libres en lo pedido → se le ofrecen alternativas", ok=False)


def _identificar_turno(ctx: Contexto, intencion: dict) -> Optional[dict]:
    """
    Pasos 6 y 7: el turno al que se refiere el paciente tiene que ser exactamente uno de sus turnos futuros.
    Ninguno → REVISION_HUMANA (no se le muestran sus turnos: la identidad es solo por DNI, design D4).
    Varios → PENDIENTE, preguntando qué día era, sin listarlos.
    """
    extraccion = ctx.extraccion
    fecha, se_entendio = _convertir(ctx, intencion, extraccion["fecha_turno_actual"], "turno actual")
    if not se_entendio:
        intencion.update(estado=PENDIENTE, motivo="varios_turnos")
        ctx.pendientes.append({"motivo": "varios_turnos"})
        return None

    nombre = f"Verificar el turno ({intencion['intencion']})"
    futuros = herramientas.turnos_futuros(ctx.dni, ctx.datos)
    if not futuros:
        intencion.update(estado=REVISION_HUMANA, motivo="sin_turnos_futuros")
        ctx.traza.registrar(7, nombre, SENSOR, "el paciente no tiene turnos futuros", ok=False)
        return None

    candidatos = [t for t in futuros if herramientas.coincide_profesional(extraccion["profesional"], t["profesional"])]
    if fecha is not None:
        candidatos = [t for t in candidatos
                      if fecha.desde.isoformat() <= t["fecha"] <= fecha.hasta.isoformat()
                      and (fecha.hora is None or t["hora"] == fecha.hora)
                      and (fecha.franja is None or fecha.franja[0] <= t["hora"] < fecha.franja[1])]
    if not candidatos:
        intencion.update(estado=REVISION_HUMANA, motivo="turno_no_coincide")
        ctx.traza.registrar(7, nombre, SENSOR, "ningún turno futuro del paciente coincide con lo que mencionó", ok=False)
        return None
    if len(candidatos) > 1:
        intencion.update(estado=PENDIENTE, motivo="varios_turnos")
        ctx.pendientes.append({"motivo": "varios_turnos"})
        ctx.traza.registrar(7, nombre, SENSOR, f"{len(candidatos)} turnos posibles → se le pregunta cuál", ok=False)
        return None
    turno = candidatos[0]
    ctx.traza.registrar(7, nombre, SENSOR, f"turno identificado: {turno['id']} ({_describir(turno)})")
    return turno


def _cargo(ctx: Contexto, intencion: dict, turno: dict) -> None:
    """Paso 8 · Regla: cargo según la política, solo para reprogramar y cancelar."""
    ahora = herramientas.ahora(ctx.datos)
    momento = datetime.fromisoformat(f"{turno['fecha']}T{turno['hora']}")
    cargo = reglas.calcular_cargo(intencion["intencion"], momento, ahora, herramientas.politica_cargos(ctx.datos))
    intencion["cargo"] = cargo
    horas = (momento - ahora).total_seconds() / 3600
    detalle = f"cargo de ${cargo:,}".replace(",", ".") if cargo else "sin cargo"
    ctx.traza.registrar(8, f"Cargo por anticipación ({intencion['intencion']})", REGLA, f"faltan {horas:.0f} h → {detalle}")


def _confirmacion(ctx: Contexto, intencion: dict) -> None:
    """Paso 9 · Regla: una operación que escribe nunca se ejecuta; queda esperando que el paciente confirme."""
    if intencion["estado"] == PENDIENTE_CONFIRMACION:
        ctx.traza.registrar(9, f"Confirmación ({intencion['intencion']})", REGLA,
                            "la operación escribe en la agenda → PENDIENTE_CONFIRMACION (no se ejecuta)")


def _fecha_deseada(ctx: Contexto, intencion: dict) -> tuple[Optional[FechaConvertida], bool]:
    fecha, se_entendio = _convertir(ctx, intencion, ctx.extraccion["fecha_deseada"], "fecha deseada")
    if not se_entendio:
        intencion.update(estado=PENDIENTE, motivo="fecha_no_entendida")
        ctx.pendientes.append({"motivo": "fecha_no_entendida"})
    return fecha, se_entendio


def resolver_intencion(ctx: Contexto, intencion: dict) -> None:
    """Pasos 6 a 9 de una intención administrativa."""
    nombre, extraccion = intencion["intencion"], ctx.extraccion

    if nombre == "consultar_resultado":
        estudios = herramientas.buscar_estudios(ctx.dni, extraccion["estudio"], ctx.datos)
        paso = f"Verificar el estudio ({nombre})"
        if not estudios:
            intencion.update(estado=REVISION_HUMANA, motivo="estudio_no_registrado")
            ctx.traza.registrar(7, paso, SENSOR, "el paciente no tiene registrado ese estudio", ok=False)
        elif len(estudios) > 1:
            intencion.update(estado=PENDIENTE, motivo="varios_estudios")
            ctx.pendientes.append({"motivo": "varios_estudios"})
            ctx.traza.registrar(7, paso, SENSOR, f"{len(estudios)} estudios posibles → se le pregunta cuál", ok=False)
        else:
            e = estudios[0]
            intencion.update(estado=COMPLETADO, estudio={"estudio": e["estudio"], "estado": e["estado"],
                                                         "entrega_estimada": e["entrega_estimada"]})
            ctx.traza.registrar(7, paso, SENSOR, f"{e['estudio']}: {e['estado']}")
        return

    if nombre in ("consultar_disponibilidad", "crear_turno"):
        fecha, se_entendio = _fecha_deseada(ctx, intencion)
        if not se_entendio:
            return
        estado = COMPLETADO if nombre == "consultar_disponibilidad" else PENDIENTE_CONFIRMACION
        _ofrecer(ctx, intencion, fecha, extraccion["profesional"], estado)
        _confirmacion(ctx, intencion)
        return

    # modificar_turno / cancelar_turno: primero, el turno que ya tiene
    turno = _identificar_turno(ctx, intencion)
    if turno is None:
        return
    intencion["turno"] = _con_sede(turno, ctx.datos)
    if nombre == "modificar_turno":
        fecha, se_entendio = _fecha_deseada(ctx, intencion)
        if not se_entendio:
            return
        _ofrecer(ctx, intencion, fecha, turno["profesional"], PENDIENTE_CONFIRMACION)
        if intencion["estado"] != PENDIENTE_CONFIRMACION:
            return
    else:
        intencion["estado"] = PENDIENTE_CONFIRMACION
    _cargo(ctx, intencion, turno)
    _confirmacion(ctx, intencion)


# ── El workflow completo ──────────────────────────────────────────────────────

def pasos_de_respuesta(ctx: Contexto, estado: str, llm: LLM) -> "redactor.Respuesta":
    """
    Pasos 10 y 11. El redactor decide si escribe una plantilla o el LLM (design D5). Solo cuando
    interviene el LLM quedan en la traza el paso 10 (redacción) y el 11 (guardrail del texto).
    """
    datos_validados = {"paciente": ctx.paciente["nombre"] if ctx.paciente else None,
                       "intenciones": ctx.intenciones, "pendientes": ctx.pendientes}
    respuesta = redactor.armar_respuesta(estado, datos_validados, llm, dni=ctx.dni)

    if respuesta.origen == "LLM":
        ctx.traza.registrar(10, "Redactar la respuesta", LLM_, f"prompt redaccion_v1: {respuesta.texto}")
        ctx.traza.registrar(11, "Verificar horarios, fechas y montos", REGLA, "todos los valores están en los datos validados")
    elif respuesta.plantilla == "respaldo" and respuesta.valores_sin_respaldo:
        ctx.traza.registrar(10, "Redactar la respuesta", LLM_, "el LLM redactó un texto")
        ctx.traza.registrar(11, "Verificar horarios, fechas y montos", REGLA,
                            "sin respaldo: " + ", ".join(respuesta.valores_sin_respaldo) + " → plantilla de respaldo",
                            ok=False)
    elif respuesta.plantilla == "respaldo":
        ctx.traza.registrar(10, "Redactar la respuesta", LLM_, f"{respuesta.detalle} → plantilla de respaldo", ok=False)
    return respuesta


def procesar(mensaje: str, llm: LLM, datos: Optional[dict] = None) -> dict:
    """
    Procesa un mensaje de punta a punta (pasos 0 a 11). Nunca rompe el programa: siempre devuelve
    un estado global, la respuesta para el paciente y la traza. El estado global es el más
    restrictivo de las intenciones (design D5); si un paso de mensaje detuvo el flujo, ese estado
    cuenta para todo el mensaje.
    """
    ctx = pasos_de_mensaje(mensaje, llm, datos)
    if not ctx.detenido:
        for intencion in ctx.intenciones:
            if intencion["estado"] is None:
                resolver_intencion(ctx, intencion)

    estados = [i["estado"] for i in ctx.intenciones]
    if ctx.detenido:
        estados.append(ctx.estado_detenido)
    estado = reglas.estado_global(estados)
    respuesta = pasos_de_respuesta(ctx, estado, llm)
    return {
        "estado": estado,
        "respuesta": respuesta,
        "paso_detenido": ctx.paso_detenido,
        "motivo_detenido": ctx.motivo_detenido,
        "paciente": ctx.paciente["nombre"] if ctx.paciente else None,
        "intenciones": ctx.intenciones,
        "pendientes": ctx.pendientes,
        "extraccion": ctx.extraccion,
        "texto_enviado_al_llm": ctx.texto_para_llm,
        "traza": ctx.traza,
        "_dni": ctx.dni,  # solo para el guardrail del paso 11: no se muestra ni se envía al LLM
    }


# ── Ejecución por consola (A.3) ───────────────────────────────────────────────
#   python entrega_3/workflow.py                       corre el lote de 9 casos (Groq si hay key; si no, simulación)
#   python entrega_3/workflow.py --simulacion          el lote con las respuestas simuladas, aunque haya key
#   python entrega_3/workflow.py --pausa 0             sin pausa entre llamadas (por defecto, 20 s)
#   python entrega_3/workflow.py "mensaje libre"       un mensaje suelto contra el LLM real

import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402

RUTA_LOTE = ENTREGA_3 / "datos" / "lote_workflow.json"
PAUSA_POR_DEFECTO = 20  # segundos entre llamadas: el límite gratuito de Groq admite ~3 por minuto (design D13)
ICONO = {REGLA: "📏", LLM_: "🤖", SENSOR: "🔎"}


def llm_simulado(respuestas: list) -> LLM:
    """Devuelve las respuestas del caso en orden, como si fueran el texto del modelo."""
    pendientes = [json.dumps(r, ensure_ascii=False) for r in respuestas if r is not None]
    return lambda system, usuario: pendientes.pop(0)


def llm_con_pausa(llm: LLM, segundos: float) -> LLM:
    """Espera `segundos` antes de cada llamada salvo la primera, para no superar el límite de la API."""
    estado = {"primera": True}

    def llamar(system: str, usuario: str) -> str:
        if not estado["primera"] and segundos > 0:
            time.sleep(segundos)
        estado["primera"] = False
        return llm(system, usuario)
    return llamar


def ocultar_org(texto: str) -> str:
    """Los errores 429 de Groq traen el ID de organización: no se guarda en la evidencia."""
    return re.sub(r"org_[A-Za-z0-9]+", "org_[OCULTO]", texto)


def imprimir(resultado: dict) -> None:
    for p in resultado["traza"].pasos:
        marca = "✔" if p.ok else "✘"
        print(f"   {marca} {p.numero:>2} {ICONO[p.tipo]} {p.tipo:<6} {p.nombre}: {ocultar_org(p.resultado)}")
    for i in resultado["intenciones"]:
        extra = f" ({i['motivo']})" if i.get("motivo") else ""
        print(f"   · {i['intencion']}: {i['estado']}{extra}")
    respuesta = resultado["respuesta"]
    origen = respuesta.origen if respuesta.origen == "LLM" else f"plantilla {respuesta.plantilla}"
    print(f"   ⇒ ESTADO: {resultado['estado']}")
    print(f"   ⇒ Respuesta al paciente ({origen}): {respuesta.texto}")


def correr_lote(llm_de_caso, pausa_descripcion: str) -> int:
    """Corre los casos del lote y devuelve cuántos dieron el estado esperado (global y por intención)."""
    lote = json.loads(RUTA_LOTE.read_text(encoding="utf-8"))
    coinciden = 0
    for caso in lote:
        print(f"── {caso['id']} · {caso['caso']} ──")
        print(f"   Mensaje: {caso['mensaje']}")
        resultado = procesar(caso["mensaje"], llm_de_caso(caso))
        imprimir(resultado)
        obtenido = {i["intencion"]: i["estado"] for i in resultado["intenciones"]}
        esperado = caso["esperado"]
        ok = resultado["estado"] == esperado["estado_global"] and obtenido == esperado["intenciones"]
        coinciden += ok
        detalle = "" if ok else f" (esperado: {esperado['estado_global']} {esperado['intenciones']})"
        print(f"   ⇒ {'COINCIDE con lo esperado' if ok else 'NO COINCIDE'}{detalle}\n")
    print(f"Resultado: {coinciden}/{len(lote)} casos con el estado esperado ({pausa_descripcion}).")
    return coinciden


def main(argv: Optional[list[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows no siempre usa UTF-8
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Workflow de la Entrega 3 (Parte A)")
    parser.add_argument("mensaje", nargs="*", help="mensaje suelto (si se omite, corre el lote)")
    parser.add_argument("--simulacion", action="store_true", help="usar las respuestas simuladas del lote")
    parser.add_argument("--pausa", type=float, default=PAUSA_POR_DEFECTO, help="segundos entre llamadas al LLM")
    args = parser.parse_args(argv)

    real = None if args.simulacion else llm_real()
    origen = real[1] if real else "SIMULACIÓN (respuestas predefinidas del lote, sin API)"
    print(f"Workflow · prompt de extracción {PROMPT_EXTRACCION} · redacción redaccion_v1 · LLM: {origen}\n")

    if args.mensaje:
        if not real:
            print("Para un mensaje suelto hace falta una API key en el .env (un mensaje nuevo no tiene respuesta simulada).")
            return 1
        imprimir(procesar(" ".join(args.mensaje), real[0]))
        return 0

    if real:
        llm = llm_con_pausa(real[0], args.pausa)  # una sola función: la pausa cuenta también entre casos
        correr_lote(lambda caso: llm, f"pausa de {args.pausa:g} s entre llamadas")
    else:
        correr_lote(lambda caso: llm_simulado([caso["simulacion"]["extraccion"], caso["simulacion"]["redaccion"]]),
                    "simulación")
    return 0


if __name__ == "__main__":
    sys.exit(main())
