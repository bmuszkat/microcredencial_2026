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
