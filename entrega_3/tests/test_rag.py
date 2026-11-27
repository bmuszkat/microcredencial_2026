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
