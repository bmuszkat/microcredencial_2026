"""Estructura de los sets de preguntas del RAG, que se commitean antes de cualquier medición o corrida real."""

import json
import re
from pathlib import Path

import pytest

ENTREGA_3 = Path(__file__).resolve().parents[1]


def cargar(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def corpus():
    return {d["id"]: d for d in cargar(ENTREGA_3 / "corpus" / "corpus_clinica.json")}


# ── Calibración del umbral (tarea 4.1, design D6) ─────────────────────────────

@pytest.fixture(scope="module")
def calibracion():
    return cargar(ENTREGA_3 / "datos" / "preguntas_calibracion.json")["preguntas"]


def test_calibracion_ids_unicos_y_tipos_validos(calibracion):
    ids = [p["id"] for p in calibracion]
    assert len(ids) == len(set(ids))
    for p in calibracion:
        assert set(p) == {"id", "tipo", "pregunta", "documento_esperado", "por_que"}, p["id"]
        assert p["tipo"] in ("dentro", "fuera"), p["id"]
        assert p["pregunta"].strip() and p["por_que"].strip(), p["id"]


def test_calibracion_tiene_suficientes_preguntas_de_cada_tipo(calibracion):
    tipos = [p["tipo"] for p in calibracion]
    assert tipos.count("dentro") >= 10
    assert tipos.count("fuera") >= 6


def test_calibracion_dentro_apunta_a_un_documento_vigente(calibracion, corpus):
    for p in calibracion:
        if p["tipo"] == "dentro":
            assert p["documento_esperado"] in corpus, p["id"]
            assert corpus[p["documento_esperado"]]["metadatos"]["vigente"], p["id"]
        else:
            assert p["documento_esperado"] is None, p["id"]


def test_calibracion_cubre_todos_los_documentos_vigentes(calibracion, corpus):
    esperados = {p["documento_esperado"] for p in calibracion if p["tipo"] == "dentro"}
    vigentes = {i for i, d in corpus.items() if d["metadatos"]["vigente"]}
    assert esperados == vigentes


def test_calibracion_no_copia_las_preguntas_de_ejemplo_del_corpus(calibracion, corpus):
    # Si se copiaran, la similitud saldría inflada y el umbral quedaría mal calibrado.
    ejemplos = set()
    for d in corpus.values():
        ejemplos |= {e.strip(" ¿?.").lower() for e in re.findall(r"¿[^?]+\?", d["descripcion_semantica"])}
    for p in calibracion:
        assert p["pregunta"].strip(" ¿?.").lower() not in ejemplos, p["id"]


# ── Comparación B.3 (tarea 6.1, design D14) ───────────────────────────────────

RAIZ = ENTREGA_3.parent


@pytest.fixture(scope="module")
def comparacion():
    return cargar(ENTREGA_3 / "datos" / "preguntas_comparacion.json")["preguntas"]


def test_comparacion_estructura(comparacion):
    ids = [p["id"] for p in comparacion]
    assert len(ids) == len(set(ids)) and len(ids) >= 2
    for p in comparacion:
        assert set(p) == {"id", "pregunta", "tipo", "esperado_rag", "entrega_1", "simulacion_sin_grounding"}, p["id"]
        assert set(p["esperado_rag"]) == {"estado", "documento", "debe_contener", "no_debe_contener"}, p["id"]
        assert p["tipo"] in ("dentro", "fuera") and p["simulacion_sin_grounding"].strip(), p["id"]


def test_comparacion_tiene_dos_preguntas_de_la_entrega_1_y_una_fuera_del_corpus(comparacion):
    assert sum(bool(p["entrega_1"]) for p in comparacion) >= 2
    assert any(p["tipo"] == "fuera" for p in comparacion)


def test_las_citas_de_la_entrega_1_son_literales(comparacion):
    for p in comparacion:
        for e in p["entrega_1"]:
            texto = (RAIZ / e["archivo"]).read_text(encoding="utf-8")
            assert e["cita"] in texto, (p["id"], e["archivo"])


def test_lo_esperado_dentro_del_corpus_sale_del_documento_vigente(comparacion, corpus):
    for p in comparacion:
        esperado = p["esperado_rag"]
        if p["tipo"] == "dentro":
            assert esperado["estado"] == "respondida", p["id"]
            doc = corpus[esperado["documento"]]
            assert doc["metadatos"]["vigente"], p["id"]
            assert esperado["debe_contener"], p["id"]
            assert any(t in doc["descripcion_semantica"] for t in esperado["debe_contener"]), p["id"]
            assert not any(t in doc["descripcion_semantica"] for t in esperado["no_debe_contener"]), p["id"]
        else:
            assert esperado["estado"] == "sin_informacion" and esperado["documento"] is None, p["id"]


def test_la_pregunta_fuera_del_corpus_no_esta_en_la_calibracion_como_dentro(comparacion, calibracion):
    dentro = {p["pregunta"].lower() for p in calibracion if p["tipo"] == "dentro"}
    for p in comparacion:
        if p["tipo"] == "fuera":
            assert p["pregunta"].lower() not in dentro
