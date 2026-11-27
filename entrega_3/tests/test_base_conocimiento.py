"""
Base de conocimiento (spec `base-conocimiento`, design D2, D4 y D5).

Usa el modelo de embeddings REAL (local, sin API key) sobre índices en carpetas temporales:
nunca toca entrega_3/indice_chroma/. El modelo se carga una vez por sesión de pytest.
La primera corrida en una máquina nueva baja el modelo (unos 640 MB).
"""

import json
import shutil

import pytest

# Sin las dependencias del RAG (por ejemplo en Python 3.14 o más nuevo, donde no instala ChromaDB)
# se saltean estos tests en lugar de romper toda la suite: la Entrega 2 y la Parte A no las necesitan.
pytest.importorskip("chromadb", reason="falta ChromaDB: usar el .venv con Python 3.12 (ver README)")
pytest.importorskip("fastembed", reason="falta fastembed: usar el .venv con Python 3.12 (ver README)")

from langchain_core.embeddings import Embeddings  # noqa: E402

import base_conocimiento as bc  # noqa: E402


class EmbeddingsContados(Embeddings):
    """Envuelve los embeddings reales y cuenta cuántos documentos se vectorizan."""

    def __init__(self, reales):
        self.reales = reales
        self.modelo = reales.modelo
        self.documentos = 0

    def embed_documents(self, textos):
        self.documentos += len(textos)
        return self.reales.embed_documents(textos)

    def embed_query(self, texto):
        return self.reales.embed_query(texto)


@pytest.fixture(scope="session")
def embeddings():
    return bc.obtener_embeddings()


@pytest.fixture(scope="module")
def base(embeddings, tmp_path_factory):
    return bc.abrir(carpeta=tmp_path_factory.mktemp("indice"), embeddings=embeddings, avisar=None)


@pytest.fixture
def corpus_copia(tmp_path):
    ruta = tmp_path / "corpus.json"
    shutil.copy(bc.RUTA_CORPUS, ruta)
    return ruta


# ── Del corpus al índice ──────────────────────────────────────────────────────

def test_cada_documento_lleva_titulo_texto_e_id_en_los_metadatos():
    documentos = bc.cargar_corpus()
    crudo = json.loads(bc.RUTA_CORPUS.read_text(encoding="utf-8"))
    assert len(documentos) == len(crudo)
    for doc, original in zip(documentos, crudo):
        assert doc.page_content.startswith(original["titulo"])
        assert original["descripcion_semantica"] in doc.page_content
        assert doc.metadata["id"] == original["id"]
        assert doc.metadata["vigente"] == original["metadatos"]["vigente"]


def test_la_huella_cambia_con_el_corpus_y_con_el_modelo(corpus_copia):
    antes = bc.huella(corpus_copia)
    assert bc.huella(corpus_copia, "otro/modelo") != antes
    corpus_copia.write_text(corpus_copia.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert bc.huella(corpus_copia) != antes


def test_primera_indexacion_guarda_todo_el_corpus(embeddings, corpus_copia, tmp_path):
    contados = EmbeddingsContados(embeddings)
    base = bc.abrir(corpus_copia, tmp_path / "indice", contados, avisar=None)
    total = len(bc.cargar_corpus(corpus_copia))
    assert contados.documentos == total
    guardado = base.get(include=["embeddings", "documents", "metadatas"])
    assert len(guardado["ids"]) == total
    # Chroma guarda las dos cosas: el vector (para buscar) y el texto (para el LLM)
    assert len(guardado["embeddings"][0]) == 768
    assert all(guardado["documents"])


def test_sin_cambios_reutiliza_el_indice(embeddings, corpus_copia, tmp_path):
    bc.abrir(corpus_copia, tmp_path / "indice", embeddings, avisar=None)
    contados = EmbeddingsContados(embeddings)
    bc.abrir(corpus_copia, tmp_path / "indice", contados, avisar=None)
    assert contados.documentos == 0


def test_corpus_modificado_reconstruye_el_indice(embeddings, corpus_copia, tmp_path):
    bc.abrir(corpus_copia, tmp_path / "indice", embeddings, avisar=None)
    corpus = json.loads(corpus_copia.read_text(encoding="utf-8"))
    doc = next(d for d in corpus if d["id"] == "DOC-TURNO")
    doc["descripcion_semantica"] += " La clínica tiene estacionamiento gratuito para pacientes en el subsuelo."
    corpus_copia.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")

    contados = EmbeddingsContados(embeddings)
    base = bc.abrir(corpus_copia, tmp_path / "indice", contados, avisar=None)
    assert contados.documentos == len(corpus)
    primero = bc.buscar(base, "¿tienen estacionamiento para dejar el auto?")[0]
    assert primero.id == "DOC-TURNO" and "estacionamiento" in primero.texto


# ── Recuperación ──────────────────────────────────────────────────────────────

def test_la_politica_de_cargos_vigente_sale_primera(base):
    recuperados = bc.buscar(base, "¿me cobran si cancelo el turno a último momento?")
    assert recuperados[0].id == "CAR-CANCELACION-V2"


@pytest.mark.parametrize("pregunta, esperado", [
    ("¿OSDE 210 cubre el campo visual?", "COB-OSDE"),
    ("¿qué tengo que llevar el día del turno?", "DOC-TURNO"),
    ("¿puedo ir manejando al fondo de ojo?", "PREP-FONDO-DE-OJO"),
    ("¿hasta qué hora atienden los sábados en la sede Centro?", "SEDE-CENTRO"),
])
def test_cada_pregunta_recupera_su_documento_primero(base, pregunta, esperado):
    assert bc.buscar(base, pregunta)[0].id == esperado


def test_k_documentos_ordenados_por_similitud(base):
    for k in (1, 3, 5):
        recuperados = bc.buscar(base, "¿cuándo está listo mi estudio?", k=k)
        assert len(recuperados) == k
        similitudes = [r.similitud for r in recuperados]
        assert similitudes == sorted(similitudes, reverse=True)
        assert all(0 <= s <= 1 for s in similitudes)


def test_por_defecto_trae_k_igual_a_3(base):
    assert len(bc.buscar(base, "¿qué cubre IOMA?")) == bc.K == 3


# ── Filtrado híbrido ──────────────────────────────────────────────────────────

def test_la_version_derogada_no_se_recupera_con_el_filtro(base):
    recuperados = bc.buscar(base, "¿me cobran si cancelo el turno a último momento?", k=15)
    assert all(r.metadatos["vigente"] for r in recuperados)
    assert "CAR-CANCELACION-V1" not in {r.id for r in recuperados}


def test_sin_filtro_la_derogada_aparece(base):
    ids = [r.id for r in bc.buscar(base, "¿me cobran si cancelo el turno a último momento?", filtro=None)]
    assert "CAR-CANCELACION-V1" in ids   # es el filtro lo que la excluye, no la similitud


def test_filtro_por_categoria(base):
    filtro = {"vigente": True, "categoria": "preparacion_estudio"}
    recuperados = bc.buscar(base, "¿cómo me preparo?", k=5, filtro=filtro)
    assert recuperados
    assert all(r.metadatos["categoria"] == "preparacion_estudio" for r in recuperados)


def test_filtro_por_obra_social(base):
    recuperados = bc.buscar(base, "¿cubren los estudios?", filtro={"obra_social": "PAMI"})
    assert [r.id for r in recuperados] == ["COB-PAMI"]


def test_armar_filtro_combina_con_and():
    assert bc.armar_filtro(None) is None
    assert bc.armar_filtro({}) is None
    assert bc.armar_filtro({"vigente": True}) == {"vigente": True}
    assert bc.armar_filtro({"vigente": True, "sede": "Centro"}) == {"$and": [{"vigente": True}, {"sede": "Centro"}]}


def test_supera_umbral_segun_el_valor_pedido(base):
    recuperados = bc.buscar(base, "¿qué tengo que llevar el día del turno?", umbral=0.0)
    assert all(r.supera_umbral for r in recuperados)
    recuperados = bc.buscar(base, "¿qué tengo que llevar el día del turno?", umbral=1.01)
    assert not any(r.supera_umbral for r in recuperados)
