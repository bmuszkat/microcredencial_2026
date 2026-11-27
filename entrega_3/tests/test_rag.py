"""
Generación del RAG (spec `respuesta-rag`, design D7 a D10).

Sin API y sin embeddings: el buscador y el modelo son falsos e inyectados en la cadena.
"""

import pytest

pytest.importorskip("chromadb", reason="falta ChromaDB: usar el .venv con Python 3.12 (ver README)")

from langchain_core.runnables import RunnableLambda  # noqa: E402

import base_conocimiento as bc  # noqa: E402
import rag  # noqa: E402


def doc(id_, texto, similitud=0.7, umbral=bc.UMBRAL_SIMILITUD, **metadatos):
    return bc.Recuperado(id=id_, titulo=id_, texto=texto, metadatos={"vigente": True, **metadatos},
                         similitud=similitud, supera_umbral=similitud >= umbral)


CARGOS = doc("CAR-CANCELACION-V2", "Política de cancelación (vigente). Con menos de 24 horas de anticipación "
             "la clínica cobra un cargo de $12.000. Responde a: ¿me cobran?", 0.70)
TURNO = doc("DOC-TURNO", "Qué llevar el día del turno. Hay que presentar el DNI y la credencial. "
            "Responde a: ¿qué llevo?", 0.50)
LEJANO = doc("SEDE-BELGRANO", "Sede Belgrano. Atiende de lunes a viernes de 9 a 19 horas.", 0.20)


class ModeloFalso:
    """Registra los prompts que recibe y devuelve una respuesta fija."""

    def __init__(self, respuesta="Respuesta (CAR-CANCELACION-V2)"):
        self.respuesta = respuesta
        self.prompts = []
        self.runnable = RunnableLambda(self._llamar)

    def _llamar(self, prompt):
        self.prompts.append(prompt)
        return self.respuesta


def cadena_con(documentos, modelo):
    return rag.crear_cadena(lambda pregunta: documentos, modelo.runnable)


# ── Cadena LCEL (tarea 5.1) ───────────────────────────────────────────────────

def test_el_contexto_lleva_los_ids_de_los_documentos_sobre_el_umbral():
    modelo = ModeloFalso()
    cadena_con([CARGOS, TURNO, LEJANO], modelo).invoke("¿me cobran si cancelo?")
    [prompt] = modelo.prompts
    usuario = prompt.messages[-1].content
    assert "[CAR-CANCELACION-V2] Política de cancelación" in usuario
    assert "[DOC-TURNO]" in usuario
    assert "SEDE-BELGRANO" not in usuario        # debajo del umbral: no entra al contexto
    assert "<consulta>\n¿me cobran si cancelo?\n</consulta>" in usuario


def test_el_system_prompt_es_el_de_la_consigna():
    modelo = ModeloFalso()
    cadena_con([CARGOS], modelo).invoke("¿me cobran?")
    system = modelo.prompts[0].messages[0].content
    assert "Usá ÚNICAMENTE los fragmentos del corpus" in system
    assert f'"{rag.SIN_INFORMACION}"' in system


def test_la_cadena_devuelve_pregunta_documentos_y_respuesta():
    modelo = ModeloFalso("Sí, $12.000 (CAR-CANCELACION-V2)")
    r = cadena_con([CARGOS, LEJANO], modelo).invoke("¿me cobran?")
    assert r["pregunta"] == "¿me cobran?"
    assert [d.id for d in r["documentos"]] == ["CAR-CANCELACION-V2", "SEDE-BELGRANO"]
    assert r["respuesta"] == "Sí, $12.000 (CAR-CANCELACION-V2)"


def test_sin_documentos_sobre_el_umbral_el_modelo_no_se_llama():
    modelo = ModeloFalso()
    r = cadena_con([LEJANO], modelo).invoke("¿atienden a domicilio?")
    assert r["respuesta"] == rag.SIN_INFORMACION
    assert modelo.prompts == []


def test_sin_ningun_documento_tambien_da_el_fallback():
    modelo = ModeloFalso()
    assert cadena_con([], modelo).invoke("hola")["respuesta"] == rag.SIN_INFORMACION
    assert modelo.prompts == []


def test_la_simulacion_devuelve_el_primer_documento_con_su_cita():
    r = rag.crear_cadena(lambda p: [CARGOS, TURNO], rag.modelo_simulado).invoke("¿me cobran?")
    assert r["respuesta"].startswith("Según la información oficial de la clínica (CAR-CANCELACION-V2):")
    assert "$12.000" in r["respuesta"]
    assert "Responde a" not in r["respuesta"] and "Política de cancelación (vigente)" not in r["respuesta"]


def test_sin_grounding_no_recibe_contexto():
    modelo = ModeloFalso("Sí, hay un cargo.")
    assert rag.cadena_sin_grounding(modelo.runnable).invoke({"pregunta": "¿me cobran?"}) == "Sí, hay un cargo."
    [prompt] = modelo.prompts
    assert prompt.messages[-1].content == "¿me cobran?"
    assert "ÚNICAMENTE" not in prompt.messages[0].content


# ── Elección del modelo ───────────────────────────────────────────────────────

def test_sin_key_el_modelo_es_la_simulacion(monkeypatch):
    monkeypatch.setattr(rag, "detectar_proveedor", lambda: None)
    modelo, origen = rag.crear_modelo()
    assert modelo is rag.modelo_simulado and origen.startswith("SIMULACIÓN")


def test_un_proveedor_no_soportado_pasa_a_simulacion(monkeypatch):
    monkeypatch.setattr(rag, "detectar_proveedor", lambda: ("anthropic", "clave-de-prueba"))
    modelo, origen = rag.crear_modelo()
    assert modelo is rag.modelo_simulado and "anthropic" in origen


def test_groq_usa_chatopenai_con_la_url_de_groq(monkeypatch):
    monkeypatch.setattr(rag, "detectar_proveedor", lambda: ("groq", "clave-de-prueba"))
    modelo, origen = rag.crear_modelo()
    assert type(modelo).__name__ == "ChatOpenAI"
    assert str(modelo.openai_api_base).rstrip("/") == rag.URL_GROQ
    assert modelo.temperature == 0 and modelo.max_retries == 3
    assert origen == f"groq ({rag.modelo_de('groq')})"


# ── Guardrail de citas, montos y porcentajes (tarea 5.2) ──────────────────────

def test_respuesta_respaldada_se_acepta():
    estado, citas, problemas = rag.verificar_respuesta(
        "Sí: con menos de 24 horas el cargo es de $12.000 (CAR-CANCELACION-V2).", [CARGOS, TURNO])
    assert (estado, citas, problemas) == (rag.RESPONDIDA, ["CAR-CANCELACION-V2"], [])


def test_cita_de_un_documento_no_recuperado():
    estado, _, problemas = rag.verificar_respuesta("El cargo es de $12.000 (CAR-CANCELACION-V1).", [CARGOS])
    assert estado == rag.NO_VERIFICADO
    assert problemas == ["cita un documento que no se recuperó: CAR-CANCELACION-V1"]


def test_cita_de_un_documento_debajo_del_umbral_tampoco_vale():
    estado, _, problemas = rag.verificar_respuesta("Belgrano abre de 9 a 19 (SEDE-BELGRANO).", [CARGOS, LEJANO])
    assert estado == rag.NO_VERIFICADO and "SEDE-BELGRANO" in problemas[0]


def test_monto_inventado():
    estado, _, problemas = rag.verificar_respuesta(
        "Según el Punto 4.2 hay un cargo de $5.000 (CAR-CANCELACION-V2).", [CARGOS])
    assert estado == rag.NO_VERIFICADO
    assert problemas == ["monto sin respaldo en los documentos: $5.000"]


@pytest.mark.parametrize("forma", ["$12.000", "$ 12000", "12000 pesos"])
def test_el_mismo_monto_escrito_de_otra_forma_se_acepta(forma):
    estado, _, problemas = rag.verificar_respuesta(f"El cargo es de {forma} (CAR-CANCELACION-V2).", [CARGOS])
    assert estado == rag.RESPONDIDA, problemas


def test_porcentaje_inventado():
    estado, _, problemas = rag.verificar_respuesta("OSDE 210 cubre el 100 % del estudio (DOC-TURNO).", [TURNO])
    assert estado == rag.NO_VERIFICADO
    assert problemas == ["porcentaje sin respaldo en los documentos: 100 %"]


def test_respuesta_sin_citas():
    estado, citas, problemas = rag.verificar_respuesta("Tenés que traer el DNI y la credencial.", [TURNO])
    assert (estado, citas) == (rag.NO_VERIFICADO, [])
    assert problemas == ["la respuesta no cita ningún documento"]


def test_varias_citas_juntas():
    texto = "Traé el DNI (DOC-TURNO) y si cancelás tarde son $12.000 (CAR-CANCELACION-V2, DOC-TURNO)."
    estado, citas, _ = rag.verificar_respuesta(texto, [CARGOS, TURNO])
    assert estado == rag.RESPONDIDA and citas == ["DOC-TURNO", "CAR-CANCELACION-V2"]


def test_el_fallback_del_modelo_no_se_verifica():
    estado, citas, problemas = rag.verificar_respuesta(rag.SIN_INFORMACION, [CARGOS])
    assert (estado, citas, problemas) == (rag.SIN_INFORMACION_OFICIAL, [], [])


# ── ResultadoRag ──────────────────────────────────────────────────────────────

def test_resultado_respondida():
    modelo = ModeloFalso("Sí, el cargo es de $12.000 (CAR-CANCELACION-V2).")
    r = rag.responder("¿me cobran?", cadena_con([CARGOS, LEJANO], modelo), "falso")
    assert (r.estado, r.citas, r.llamo_llm, r.origen) == (rag.RESPONDIDA, ["CAR-CANCELACION-V2"], True, "falso")
    assert r.texto == "Sí, el cargo es de $12.000 (CAR-CANCELACION-V2)."
    assert r.candidatos == [("CAR-CANCELACION-V2", 0.70, True), ("SEDE-BELGRANO", 0.20, False)]


def test_resultado_sin_informacion_sin_llamar_al_llm():
    modelo = ModeloFalso()
    r = rag.responder("¿atienden a domicilio?", cadena_con([LEJANO], modelo))
    assert (r.estado, r.texto, r.llamo_llm) == (rag.SIN_INFORMACION_OFICIAL, rag.SIN_INFORMACION, False)
    assert modelo.prompts == []


def test_resultado_sin_informacion_porque_lo_dijo_el_modelo():
    r = rag.responder("¿hay descuento?", cadena_con([CARGOS], ModeloFalso(rag.SIN_INFORMACION)))
    assert (r.estado, r.texto, r.llamo_llm) == (rag.SIN_INFORMACION_OFICIAL, rag.SIN_INFORMACION, True)


def test_resultado_no_verificado_no_entrega_texto():
    inventado = "Según el Punto 4.2, son $5.000 (CAR-CANCELACION-V2)."
    r = rag.responder("¿me cobran?", cadena_con([CARGOS], ModeloFalso(inventado)))
    assert (r.estado, r.texto) == (rag.NO_VERIFICADO, None)
    assert r.texto_generado == inventado and "$5.000" in r.detalle


def test_error_de_comunicacion_no_inventa_y_oculta_la_organizacion():
    def falla(prompt):
        raise ConnectionError("Rate limit reached for org_01abcXYZ in model")
    r = rag.responder("¿me cobran?", rag.crear_cadena(lambda p: [CARGOS], RunnableLambda(falla)))
    assert (r.estado, r.texto) == (rag.ERROR, None)
    assert r.detalle == "ConnectionError: Rate limit reached for org_[OCULTO] in model"


def test_crear_respondedor_usa_la_simulacion_sin_key(monkeypatch):
    monkeypatch.setattr(rag, "detectar_proveedor", lambda: None)

    class BaseFalsa:
        pass

    monkeypatch.setattr(rag.bc, "buscar", lambda base, pregunta, filtro, umbral: [CARGOS])
    r = rag.crear_respondedor(BaseFalsa())("¿me cobran?")
    assert r.estado == rag.RESPONDIDA and r.origen.startswith("SIMULACIÓN")
    assert r.citas == ["CAR-CANCELACION-V2"]


# ── Consola (tarea 5.3) ───────────────────────────────────────────────────────

def test_preguntar_en_simulacion_muestra_recuperacion_estado_y_respuesta(monkeypatch, capsys):
    usados = {}

    def respondedor_falso(modelo=None, origen=None):
        usados["modelo"], usados["origen"] = modelo, origen
        return lambda pregunta: rag.ResultadoRag(rag.RESPONDIDA, "Traé el DNI (DOC-TURNO).", ["DOC-TURNO"],
                                                 [("DOC-TURNO", 0.711, True)], True, None, origen)

    monkeypatch.setattr(rag, "crear_respondedor", respondedor_falso)
    assert rag.main(["preguntar", "¿qué", "llevo?", "--simulacion"]) == 0
    salida = capsys.readouterr().out
    assert usados["modelo"] is rag.modelo_simulado
    assert "Pregunta:  ¿qué llevo?" in salida and "SIMULACIÓN" in salida
    assert "0.711  ✓  DOC-TURNO" in salida
    assert "Estado:    respondida" in salida and "Respuesta: Traé el DNI (DOC-TURNO)." in salida


def test_preguntar_muestra_lo_que_descarto_el_guardrail(capsys):
    r = rag.ResultadoRag(rag.NO_VERIFICADO, None, ["CAR-CANCELACION-V2"], [("CAR-CANCELACION-V2", 0.7, True)],
                         True, "monto sin respaldo en los documentos: $5.000", "falso", "Son $5.000 (CAR-CANCELACION-V2).")
    rag.imprimir_resultado(r)
    salida = capsys.readouterr().out
    assert "Detalle:   monto sin respaldo" in salida
    assert "Descartada por el guardrail: Son $5.000" in salida
    assert "Respuesta:" not in salida


# ── Comparación B.3 (tarea 6.2) ───────────────────────────────────────────────

ESPERADO_C1 = {"estado": "respondida", "documento": "CAR-CANCELACION-V2",
               "debe_contener": ["$12.000"], "no_debe_contener": ["$5.000", "48 horas"]}


def resultado(estado=rag.RESPONDIDA, texto="Sí, son $12.000 (CAR-CANCELACION-V2).", citas=("CAR-CANCELACION-V2",)):
    return rag.ResultadoRag(estado, texto, list(citas), [("CAR-CANCELACION-V2", 0.7, True)], True)


def test_evaluar_esperado_cumple():
    assert rag.evaluar_esperado(resultado(), ESPERADO_C1) == []


def test_evaluar_esperado_detecta_cada_falla():
    fallas = rag.evaluar_esperado(resultado(texto="Son $5.000 o $8.000 con 48 horas (DOC-TURNO).", citas=["DOC-TURNO"]),
                                  ESPERADO_C1)
    assert fallas == ["no cita CAR-CANCELACION-V2", "no menciona ninguno de: $12.000",
                      "menciona «$5.000»", "menciona «48 horas»"]


def test_evaluar_esperado_sin_texto_por_el_guardrail():
    fallas = rag.evaluar_esperado(resultado(rag.NO_VERIFICADO, None), ESPERADO_C1)
    assert fallas[0] == "estado no_verificado, se esperaba respondida"


def test_evaluar_esperado_fuera_del_corpus():
    esperado = {"estado": "sin_informacion", "documento": None, "debe_contener": [], "no_debe_contener": []}
    r = rag.ResultadoRag(rag.SIN_INFORMACION_OFICIAL, rag.SIN_INFORMACION, [], [], False)
    assert rag.evaluar_esperado(r, esperado) == []


def test_la_pausa_espera_entre_llamadas_salvo_la_primera(monkeypatch):
    esperas = []
    monkeypatch.setattr(rag.time, "sleep", esperas.append)
    pausa = rag.Pausa(20)
    assert [pausa(x) for x in "abc"] == ["a", "b", "c"]
    assert esperas == [20, 20]


def test_correr_comparacion_imprime_las_dos_respuestas_y_cuenta_aciertos(capsys):
    preguntas = [
        {"id": "C1", "pregunta": "¿me cobran?", "esperado_rag": ESPERADO_C1,
         "entrega_1": [{"archivo": "a2.txt", "cita": "Punto 4.2, $5.000"}]},
        {"id": "C2", "pregunta": "¿otra?", "esperado_rag": ESPERADO_C1, "entrega_1": []},
    ]
    respuestas = iter([resultado(), resultado(rag.NO_VERIFICADO, None)])
    aciertos = rag.correr_comparacion(preguntas, lambda p: next(respuestas), lambda p: f"sin datos: {p['id']}")
    salida = capsys.readouterr().out
    assert aciertos == 1
    assert "«Punto 4.2, $5.000»" in salida and "sin datos: C1" in salida
    assert "✓ cumple" in salida and "✗ estado no_verificado" in salida
    assert "Resultado: 1/2 preguntas con lo esperado con RAG" in salida
