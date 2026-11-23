"""Pruebas del evaluador (spec `evaluacion-extraccion`). No usan la API."""

import json

import pytest

import evaluar
from clinica.extractor import validar_respuesta

# ── Comparación de intenciones y entidades ─────────────────────────────────────


def test_intenciones_sin_importar_el_orden():
    assert evaluar.intenciones_correctas(["modificar_turno", "consultar_resultado"],
                                         ["consultar_resultado", "modificar_turno"])


def test_intenciones_de_mas_o_de_menos_son_incorrectas():
    assert not evaluar.intenciones_correctas(["crear_turno"], ["crear_turno", "consulta_medica"])
    assert not evaluar.intenciones_correctas(["crear_turno", "consulta_medica"], ["crear_turno"])


@pytest.mark.parametrize("nombre, esperado, obtenido, ok", [
    ("profesional", None, None, True),
    ("profesional", None, "Dra. Paz", False),          # inventó un dato
    ("profesional", None, "", True),                   # string vacío cuenta como null
    ("profesional", "Paz", None, False),               # no lo extrajo
    ("profesional", "Paz", "Dra. Paz", True),          # contiene la palabra clave
    ("fecha_deseada", "miercoles", "el Miércoles a la tarde", True),  # sin tildes ni mayúsculas
    ("fecha_deseada", "jueves", "viernes", False),
    ("dni", "30123456", "30123456", True),
    ("dni", "30123456", "30.123.456", False),          # el DNI tiene que venir normalizado
])
def test_comparacion_de_entidades(nombre, esperado, obtenido, ok):
    assert evaluar.entidad_correcta(nombre, esperado, obtenido) is ok


# ── Normalización de v1 ─────────────────────────────────────────────────────────

def test_v1_otra_mas_flag_equivale_a_consulta_medica():
    v1 = {"intenciones": ["otra"], "dni": None, "es_consulta_medica": True}
    assert evaluar.normalizar_v1(v1) == {"intenciones": ["consulta_medica"], "dni": None}


def test_v1_turno_mas_flag_suma_consulta_medica():
    v1 = {"intenciones": ["crear_turno"], "es_consulta_medica": True}
    assert evaluar.normalizar_v1(v1)["intenciones"] == ["crear_turno", "consulta_medica"]


def test_v1_sin_flag_no_cambia_las_intenciones():
    v1 = {"intenciones": ["otra"], "es_consulta_medica": False}
    assert evaluar.normalizar_v1(v1)["intenciones"] == ["otra"]


# ── Evaluación de un caso ───────────────────────────────────────────────────────

CASO = {"id": "t01", "categoria": "multi", "mensaje": "…",
        "esperado": {"intenciones": ["modificar_turno", "consultar_resultado"], "dni": "30123456",
                     "profesional": "López", "fecha_turno_actual": "jueves",
                     "fecha_deseada": "viernes", "estudio": "campo visual"}}


def resultado_desde(texto: str, version: str = "v2") -> dict:
    return {"origen": "test", "prompt": version, "respuesta_cruda": texto, **validar_respuesta(texto, version)}


def test_caso_completamente_correcto():
    texto = json.dumps({"intenciones": ["consultar_resultado", "modificar_turno"], "dni": "30123456",
                        "profesional": "Dra. López", "fecha_turno_actual": "jueves 15 hs",
                        "fecha_deseada": "viernes a la mañana", "estudio": "Campo Visual"})
    e = evaluar.evaluar_caso(CASO, resultado_desde(texto), "v2")
    assert e["intenciones_ok"] and e["completo_ok"]


def test_intenciones_bien_y_una_entidad_mal():
    texto = json.dumps({"intenciones": ["modificar_turno", "consultar_resultado"], "dni": "30123456",
                        "profesional": "Dra. López", "fecha_turno_actual": None,
                        "fecha_deseada": "viernes", "estudio": "campo visual"})
    e = evaluar.evaluar_caso(CASO, resultado_desde(texto), "v2")
    assert e["intenciones_ok"] and not e["completo_ok"]
    assert e["entidades_ok"]["fecha_turno_actual"] is False


@pytest.mark.parametrize("resultado", [
    {"ok": False, "error": "COMUNICACION", "detalle": "HTTP 429"},
    {"ok": False, "error": "FORMATO", "respuesta_cruda": "", "detalle": "x"},
    resultado_desde("{}"),   # CONTRATO
])
def test_mensaje_con_error_cuenta_como_incorrecto(resultado):
    e = evaluar.evaluar_caso(CASO, resultado, "v2")
    assert not e["intenciones_ok"] and not any(e["entidades_ok"].values()) and e["error"]


def test_error_de_regla_no_descuenta_la_extraccion():
    """Un DNI inválido copiado fielmente es un acierto de extracción (design D6)."""
    caso = {**CASO, "esperado": {**CASO["esperado"], "dni": "30123"}}
    texto = json.dumps({"intenciones": ["modificar_turno", "consultar_resultado"], "dni": "30123",
                        "profesional": "López", "fecha_turno_actual": "jueves",
                        "fecha_deseada": "viernes", "estudio": "campo visual"})
    resultado = {**resultado_desde(texto), "ok": False, "error": "REGLA", "detalle": "DNI inválido"}
    assert evaluar.evaluar_caso(caso, resultado, "v2")["completo_ok"]


def test_v1_se_evalua_normalizado():
    caso = {**CASO, "esperado": {"intenciones": ["consulta_medica"], **{k: None for k in evaluar.ENTIDADES}}}
    texto = json.dumps({"intenciones": ["otra"], "dni": None, "profesional": None, "fecha_turno_actual": None,
                        "fecha_deseada": None, "estudio": None, "es_consulta_medica": True})
    assert evaluar.evaluar_caso(caso, resultado_desde(texto, "v1"), "v1")["completo_ok"]


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_la_simulacion_cumple_el_contrato_de_cada_version(version):
    set_casos = json.loads(evaluar.RUTA_SET.read_text(encoding="utf-8"))
    for caso in set_casos:
        assert validar_respuesta(evaluar.simulacion_para(caso, version), version)["ok"], caso["id"]


# ── Corrida retomable y métricas ───────────────────────────────────────────────

def procesar_falso(llamadas: list):
    def procesar(mensaje, simulacion, version):
        llamadas.append(mensaje)
        return resultado_desde(simulacion, version)
    return procesar


def test_reanudacion_no_repite_llamadas(tmp_path):
    set_casos = json.loads(evaluar.RUTA_SET.read_text(encoding="utf-8"))[:3]
    ruta = tmp_path / "evaluacion_v2.json"
    llamadas = []
    evaluar.evaluar(set_casos[:2], "v2", ruta, pausa=0, procesar=procesar_falso(llamadas))
    assert len(llamadas) == 2 and ruta.exists()

    datos = evaluar.evaluar(set_casos, "v2", ruta, pausa=0, procesar=procesar_falso(llamadas))
    assert len(llamadas) == 3                      # solo evaluó el que faltaba
    assert set(datos["resultados"]) == {c["id"] for c in set_casos}


def test_metricas_con_simulacion_perfecta(tmp_path):
    set_casos = json.loads(evaluar.RUTA_SET.read_text(encoding="utf-8"))
    datos = evaluar.evaluar(set_casos, "v2", tmp_path / "r.json", pausa=0, procesar=procesar_falso([]))
    m = evaluar.calcular_metricas(list(datos["resultados"].values()))
    assert m["total"] == 50
    assert m["json_valido"] == m["intenciones_exactas"] == m["completamente_correctos"] == 100.0


def test_metricas_cuentan_errores_por_etapa():
    evaluados = [
        evaluar.evaluar_caso(CASO, {"ok": False, "error": "COMUNICACION"}, "v2"),
        evaluar.evaluar_caso(CASO, resultado_desde("no es json"), "v2"),
        evaluar.evaluar_caso(CASO, resultado_desde("{}"), "v2"),
        evaluar.evaluar_caso(CASO, resultado_desde(json.dumps({**CASO["esperado"]})), "v2"),
    ]
    m = evaluar.calcular_metricas(evaluados)
    assert m["json_valido"] == 50.0 and m["cumple_contrato"] == 25.0 and m["completamente_correctos"] == 25.0
    assert m["errores"] == {"COMUNICACION": 1, "FORMATO": 1, "CONTRATO": 1, "REGLA": 0}


def test_informe_markdown_lista_los_fallos(tmp_path):
    set_casos = json.loads(evaluar.RUTA_SET.read_text(encoding="utf-8"))[:2]
    datos = evaluar.evaluar(set_casos, "v2", tmp_path / "r.json", pausa=0,
                            procesar=lambda m, s, v: {"ok": False, "error": "COMUNICACION", "detalle": "x"})
    md = evaluar.informe_markdown(datos, set_casos)
    assert "Mensajes con algún error (2)" in md and set_casos[0]["id"] in md
