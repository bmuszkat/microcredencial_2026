"""Respuesta al paciente (spec `respuesta-paciente`): quién escribe, qué ve el LLM y las plantillas."""

import inspect
import json
import re
import urllib.error

import pytest

import redactor as r
from clinica.llm import RespuestaNoJSON
from reglas import COMPLETADO, DERIVADO, PENDIENTE, PENDIENTE_CONFIRMACION, REVISION_HUMANA

TURNO_JUAN = {"profesional": "Dra. López", "fecha": "2026-11-26", "hora": "15:00", "sede": "Centro"}
OPCIONES_VIERNES = [
    {"profesional": "Dra. López", "fecha": "2026-11-27", "hora": "09:00", "sede": "Centro"},
    {"profesional": "Dra. López", "fecha": "2026-11-27", "hora": "10:30", "sede": "Centro"},
]


def datos_juan(cargo: int = 0) -> dict:
    return {
        "paciente": "Juan Pérez",
        "intenciones": [
            {"intencion": "modificar_turno", "estado": PENDIENTE_CONFIRMACION,
             "turno": TURNO_JUAN, "opciones": OPCIONES_VIERNES, "opciones_alternativas": False, "cargo": cargo},
            {"intencion": "consultar_resultado", "estado": COMPLETADO,
             "estudio": {"estudio": "campo visual", "estado": "listo", "entrega_estimada": None}},
        ],
        "pendientes": [],
    }


class LLMFalso:
    """Registra lo que recibe y devuelve una respuesta fija (o lanza un error)."""

    def __init__(self, respuesta=None, error=None):
        self.respuesta, self.error, self.llamadas = respuesta, error, []

    def __call__(self, system, usuario):
        self.llamadas.append((system, usuario))
        if self.error:
            raise self.error
        return self.respuesta


OK = json.dumps({"respuesta": "Hola Juan, te ofrecemos el viernes 27/11 a las 09:00."})


# ── Quién escribe según el estado ─────────────────────────────────────────────

def test_revision_humana_es_un_acuse_fijo_sin_llamar_al_llm():
    llm = LLMFalso(OK)
    datos = {"paciente": None, "intenciones": [], "pendientes": []}
    resp = r.armar_respuesta(REVISION_HUMANA, datos, llm)
    assert (resp.texto, resp.origen, resp.plantilla) == (r.ACUSE_REVISION, "PLANTILLA", "acuse_revision")
    assert llm.llamadas == []


def test_pendiente_sin_dni_pide_el_dni_sin_llamar_al_llm():
    llm = LLMFalso(OK)
    datos = {"paciente": None, "intenciones": [], "pendientes": [{"motivo": "falta_dni"}]}
    resp = r.armar_respuesta(PENDIENTE, datos, llm)
    assert resp.plantilla == "preguntas" and "DNI" in resp.texto
    assert llm.llamadas == []


def test_consulta_medica_sola_es_la_plantilla_de_derivacion():
    llm = LLMFalso(OK)
    datos = {"paciente": None, "intenciones": [{"intencion": "consulta_medica", "estado": DERIVADO}], "pendientes": []}
    resp = r.armar_respuesta(DERIVADO, datos, llm)
    assert (resp.texto, resp.plantilla) == (r.DERIVACION, "derivacion")
    assert llm.llamadas == []


def test_otra_es_la_plantilla_de_fuera_de_alcance():
    llm = LLMFalso(OK)
    datos = {"paciente": None, "pendientes": [],
             "intenciones": [{"intencion": "otra", "estado": COMPLETADO, "motivo": "fuera_de_alcance"}]}
    resp = r.armar_respuesta(COMPLETADO, datos, llm)
    assert (resp.texto, resp.plantilla) == (r.FUERA_DE_ALCANCE, "fuera_de_alcance")
    assert llm.llamadas == []


def test_pendiente_confirmacion_la_redacta_el_llm():
    llm = LLMFalso(OK)
    resp = r.armar_respuesta(PENDIENTE_CONFIRMACION, datos_juan(), llm)
    assert resp.origen == "LLM"
    assert resp.texto == json.loads(OK)["respuesta"]
    assert len(llm.llamadas) == 1


def test_derivado_mixto_lo_redacta_el_llm_y_avisa_la_derivacion():
    llm = LLMFalso(OK)
    datos = {"paciente": "Ana Torres", "pendientes": [], "intenciones": [
        {"intencion": "crear_turno", "estado": PENDIENTE_CONFIRMACION, "opciones": OPCIONES_VIERNES},
        {"intencion": "consulta_medica", "estado": DERIVADO},
    ]}
    resp = r.armar_respuesta(PENDIENTE_CONFIRMACION, datos, llm)
    assert resp.origen == "LLM"
    assert "avisar_derivacion" in llm.llamadas[0][1]


# ── Qué ve el LLM redactor ────────────────────────────────────────────────────

def test_el_redactor_no_recibe_el_mensaje_original():
    # La función no tiene ningún parámetro por donde pueda entrar el mensaje del paciente.
    assert "mensaje" not in inspect.signature(r.armar_respuesta).parameters
    llm = LLMFalso(OK)
    r.armar_respuesta(PENDIENTE_CONFIRMACION, datos_juan(), llm)
    system, usuario = llm.llamadas[0]
    assert system == r.PROMPT_REDACCION.read_text(encoding="utf-8")
    assert usuario.startswith("Datos validados (JSON):")
    assert json.loads(usuario.split("\n", 1)[1]) == r.vista_para_llm(datos_juan())


def test_la_vista_trae_los_valores_ya_formateados():
    vista = r.vista_para_llm(datos_juan(cargo=12000))
    reprogramar = vista["pedidos"][0]
    assert reprogramar["que_hacer"] == "ofrecer_y_pedir_confirmacion"
    assert reprogramar["turno_actual"] == {"dia": "jueves 26/11", "hora": "15:00", "profesional": "Dra. López", "sede": "Centro"}
    assert [o["dia"] for o in reprogramar["opciones"]] == ["viernes 27/11", "viernes 27/11"]
    assert reprogramar["cargo"] == "$12.000"
    assert vista["pedidos"][1]["estudio"] == {"nombre": "campo visual", "estado": "está listo para retirar"}


def test_sin_cargo_la_vista_no_trae_ningun_monto():
    assert r.vista_para_llm(datos_juan(cargo=0))["pedidos"][0]["cargo"] == "sin cargo"


def test_el_prompt_pide_formato_fijo_y_prohibe_confirmar():
    prompt = r.PROMPT_REDACCION.read_text(encoding="utf-8")
    for regla in ("dd/mm", "HH:MM", "$12.000", "NO está hecho", "No des opiniones médicas"):
        assert regla in prompt


# ── Plantilla de respaldo cuando falla la redacción ───────────────────────────

@pytest.mark.parametrize("llm, tipo", [
    (LLMFalso(json.dumps({"texto": "hola"})), "CONTRATO"),          # clave fuera del contrato
    (LLMFalso(json.dumps({"respuesta": ""})), "CONTRATO"),          # texto vacío
    (LLMFalso("¡Claro! Hola Juan"), "FORMATO"),                     # no es JSON
    (LLMFalso(error=RespuestaNoJSON("json_validate_failed", "x")), "FORMATO"),
    (LLMFalso(error=OSError("sin red")), "COMUNICACION"),
    (LLMFalso(error=urllib.error.HTTPError("u", 429, "Too Many Requests", None, None)), "COMUNICACION"),
])
def test_falla_de_redaccion_usa_la_plantilla_de_respaldo(llm, tipo):
    resp = r.armar_respuesta(PENDIENTE_CONFIRMACION, datos_juan(), llm)
    assert (resp.origen, resp.plantilla) == ("PLANTILLA", "respaldo")
    assert resp.detalle.startswith(tipo)


def test_sin_llm_usa_la_plantilla_de_respaldo():
    resp = r.armar_respuesta(PENDIENTE_CONFIRMACION, datos_juan(), None)
    assert resp.plantilla == "respaldo"


def test_el_respaldo_tiene_los_mismos_datos():
    texto = r.plantilla_respaldo(datos_juan(cargo=12000))
    for dato in ("Juan Pérez", "jueves 26/11 a las 15:00", "viernes 27/11 a las 09:00", "10:30",
                 "$12.000", "campo visual está listo para retirar"):
        assert dato in texto
    assert "se reprogramó" not in texto and "confirmado" not in texto


def test_el_respaldo_sin_cargo_no_menciona_montos():
    assert "$" not in r.plantilla_respaldo(datos_juan(cargo=0))


def test_el_respaldo_de_un_estudio_en_proceso_da_la_entrega_estimada():
    datos = {"paciente": None, "pendientes": [], "intenciones": [{
        "intencion": "consultar_resultado", "estado": COMPLETADO,
        "estudio": {"estudio": "OCT", "estado": "en_proceso", "entrega_estimada": "2026-11-27"}}]}
    assert "estaría listo el viernes 27/11" in r.plantilla_respaldo(datos)


# ── Las plantillas no exponen motivos internos ni datos registrados ───────────

FIJAS = [r.ACUSE_REVISION, r.DERIVACION, r.FUERA_DE_ALCANCE, *r.PREGUNTAS.values()]
INTERNO = re.compile(r"padr[oó]n|REVISION|CONTRATO|FORMATO|COMUNICACION|no registrado|no coincide|motivo", re.I)


@pytest.mark.parametrize("texto", FIJAS)
def test_las_plantillas_fijas_no_exponen_motivos_internos(texto):
    assert not INTERNO.search(texto)


@pytest.mark.parametrize("texto", FIJAS)
def test_las_plantillas_fijas_no_muestran_fechas_ni_horas(texto):
    # ningún turno ni estudio registrado: sin fechas, horas ni montos
    assert not re.search(r"\d", texto)


def test_la_pregunta_por_varios_turnos_no_los_lista():
    texto = r.plantilla_preguntas([{"motivo": "varios_turnos"}])
    assert "¿Qué día y a qué hora era el turno" in texto
    assert not re.search(r"\d", texto)


def test_sin_turnos_en_lo_pedido_ofrece_turnos_libres():
    texto = r.plantilla_preguntas([{"motivo": "sin_turnos_en_lo_pedido", "opciones": OPCIONES_VIERNES}])
    assert "viernes 27/11 a las 09:00" in texto


def test_preguntas_repetidas_aparecen_una_vez():
    texto = r.plantilla_preguntas([{"motivo": "falta_dni"}, {"motivo": "falta_dni"}])
    assert texto.count("DNI") == 1


# ── Formato ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("iso, esperado", [("2026-11-27", "viernes 27/11"), ("2026-12-02", "miércoles 02/12")])
def test_fecha_corta(iso, esperado):
    assert r.fecha_corta(iso) == esperado


@pytest.mark.parametrize("valor, esperado", [(12000, "$12.000"), (500, "$500"), (1200000, "$1.200.000")])
def test_monto(valor, esperado):
    assert r.monto(valor) == esperado


# ── Guardrail del texto redactado (paso 11, design D11) ───────────────────────

def redactado(texto: str) -> LLMFalso:
    return LLMFalso(json.dumps({"respuesta": texto}))


def test_texto_respaldado_por_los_datos_llega_al_paciente():
    texto = ("¡Hola, Juan! Tu turno del jueves 26/11 a las 15:00 con la Dra. López se puede pasar al "
             "viernes 27/11 a las 09:00 o a las 10:30. No tiene cargo. Tu campo visual está listo para retirar.")
    resp = r.armar_respuesta(PENDIENTE_CONFIRMACION, datos_juan(), redactado(texto))
    assert (resp.origen, resp.texto, resp.valores_sin_respaldo) == ("LLM", texto, [])


def test_monto_inventado_usa_la_plantilla_y_registra_el_valor():
    resp = r.armar_respuesta(PENDIENTE_CONFIRMACION, datos_juan(cargo=0),
                             redactado("Hola Juan, el cambio tiene un cargo de $5.000."))
    assert resp.plantilla == "respaldo" and resp.detalle.startswith("GUARDRAIL")
    assert resp.valores_sin_respaldo == ["$5.000"]


def test_monto_distinto_al_de_la_politica_se_rechaza():
    sin_respaldo = r.verificar_texto("Tiene un cargo de $5.000.", datos_juan(cargo=12000))
    assert "$5.000" in sin_respaldo and "falta el cargo $12.000" in sin_respaldo


def test_horario_inventado_usa_la_plantilla():
    resp = r.armar_respuesta(PENDIENTE_CONFIRMACION, datos_juan(),
                             redactado("Hola Juan, te ofrecemos el viernes 27/11 a las 11:30."))
    assert resp.plantilla == "respaldo"
    assert resp.valores_sin_respaldo == ["11:30"]


def test_cargo_omitido_usa_la_plantilla():
    resp = r.armar_respuesta(PENDIENTE_CONFIRMACION, datos_juan(cargo=12000),
                             redactado("Hola Juan, podés pasarlo al viernes 27/11 a las 09:00."))
    assert resp.plantilla == "respaldo"
    assert resp.valores_sin_respaldo == ["falta el cargo $12.000"]


def test_sin_cargo_cualquier_monto_se_rechaza():
    assert r.verificar_texto("No tiene cargo, son $0.", datos_juan(cargo=0)) == ["$0"]


@pytest.mark.parametrize("fecha", ["28 de noviembre", "28/11", "sábado 28"])
def test_fecha_inventada_se_rechaza_en_cualquier_formato(fecha):
    assert r.verificar_texto(f"Te ofrecemos el {fecha} a las 09:00.", datos_juan()) == [fecha]


@pytest.mark.parametrize("fecha", ["27 de noviembre", "27/11", "viernes 27", "viernes 27/11"])
def test_fecha_respaldada_en_cualquier_formato(fecha):
    assert r.verificar_texto(f"Te ofrecemos el {fecha} a las 09:00.", datos_juan()) == []


def test_dia_de_la_semana_que_no_coincide_con_la_fecha():
    # el 27/11 es viernes: "jueves 27" no está respaldado
    assert r.verificar_texto("el jueves 27 a las 09:00", datos_juan()) == ["jueves 27"]


@pytest.mark.parametrize("hora", ["15:00", "15 hs", "15hs", "a las 15"])
def test_formas_de_un_horario_respaldado(hora):
    assert r.verificar_texto(f"Tu turno del jueves 26/11 {hora} con la Dra. López.", datos_juan()) == []


@pytest.mark.parametrize("hora, normalizada", [("a las 11", "11:00"), ("9.30", "09:30"), ("16 hs", "16:00")])
def test_formas_de_un_horario_sin_respaldo(hora, normalizada):
    datos = datos_juan()
    assert r.valores_del_texto(f"el viernes 27/11 {hora}")[2] == [(hora, normalizada)]
    assert r.verificar_texto(f"el viernes 27/11 {hora}", datos) == [hora]


@pytest.mark.parametrize("escrito", ["$12.000", "$ 12000", "$12000", "12.000 pesos"])
def test_formas_del_cargo_respaldado(escrito):
    assert r.verificar_texto(f"Tiene un cargo de {escrito}.", datos_juan(cargo=12000)) == []


def test_un_monto_no_se_lee_como_hora_ni_fecha():
    montos, fechas, horas = r.valores_del_texto("cargo de $12.000")
    assert (montos, fechas, horas) == ([("$12.000", 12000)], [], [])


def test_menos_de_24_horas_no_es_un_horario():
    assert r.verificar_texto("Como faltan menos de 24 horas, tiene un cargo de $12.000.", datos_juan(cargo=12000)) == []
    assert r.verificar_texto("Faltan menos de 24 hs.", datos_juan()) == []


def test_entrega_estimada_de_un_estudio_es_una_fecha_respaldada():
    datos = {"paciente": None, "pendientes": [], "intenciones": [{
        "intencion": "consultar_resultado", "estado": COMPLETADO,
        "estudio": {"estudio": "OCT", "estado": "en_proceso", "entrega_estimada": "2026-11-27"}}]}
    assert r.verificar_texto("Tu OCT estaría listo el viernes 27/11.", datos) == []


@pytest.mark.parametrize("escrito", ["30.123.456", "30123456", "30 123 456"])
def test_el_dni_en_el_texto_usa_la_plantilla(escrito):
    resp = r.armar_respuesta(PENDIENTE_CONFIRMACION, datos_juan(),
                             redactado(f"Hola Juan (DNI {escrito}), tu campo visual está listo."), dni="30123456")
    assert resp.plantilla == "respaldo"
    assert "DNI del paciente" in resp.valores_sin_respaldo


@pytest.mark.parametrize("cargo", [0, 12000])
def test_la_plantilla_de_respaldo_pasa_su_propio_guardrail(cargo):
    datos = datos_juan(cargo=cargo)
    assert r.verificar_texto(r.plantilla_respaldo(datos), datos, dni="30123456") == []


def test_hora_despues_de_una_fecha_no_se_lee_como_dia():
    _, fechas, horas = r.valores_del_texto("el viernes 27/11 16 hs")
    assert fechas == [("27/11", (27, 11, None))]
    assert horas == [("16 hs", "16:00")]
