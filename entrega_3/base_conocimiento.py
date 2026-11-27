"""
Base de conocimiento del RAG: embeddings locales + ChromaDB (spec `base-conocimiento`).

El RAG tiene dos momentos:

    [OFFLINE · una vez]   corpus JSON → Document → embedding → ChromaDB (queda en disco)
                          indexar()
    [ONLINE · cada vez]   pregunta → embedding → los k más parecidos (solo vigentes) → ¿superan el umbral?
                          buscar()

Los embeddings se calculan EN LA COMPU, sin API key, con un modelo entrenado en español
(jinaai/jina-embeddings-v2-base-es, vía fastembed). La primera vez se baja (unos 640 MB) y queda
en la caché. Por eso la búsqueda funciona igual con o sin key: solo la generación usa el LLM.

Qué guarda Chroma por documento: el id, el vector (768 números), el texto y los metadatos.
El vector sirve para BUSCAR; el texto es lo que después lee el LLM; los metadatos sirven
para FILTRAR (por ejemplo, nunca recuperar una política derogada).
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

ENTREGA_3 = Path(__file__).resolve().parent
RUTA_CORPUS = ENTREGA_3 / "corpus" / "corpus_clinica.json"
CARPETA_INDICE = ENTREGA_3 / "indice_chroma"      # en el .gitignore: se regenera desde el corpus
COLECCION = "corpus_clinica"

MODELO_EMBEDDINGS = os.getenv("EMBEDDINGS_MODEL", "jinaai/jina-embeddings-v2-base-es")
CACHE_MODELOS = Path.home() / ".cache" / "fastembed"

K = 3                          # cuántos documentos se recuperan
SOLO_VIGENTES = {"vigente": True}   # filtrado híbrido por defecto: nunca una política derogada
UMBRAL_SIMILITUD = 0.35        # PROVISORIO (el de la cátedra con el mismo modelo); se calibra en la tarea 4.2

logging.getLogger("chromadb").setLevel(logging.ERROR)


# ── Embeddings: texto → vector ────────────────────────────────────────────────

class EmbeddingsLocales(Embeddings):
    """Implementa la interfaz Embeddings de LangChain sobre fastembed, así Chroma lo puede usar."""

    def __init__(self, modelo: str = MODELO_EMBEDDINGS):
        from fastembed import TextEmbedding   # import acá: el modelo solo se carga si se usa
        self.modelo = modelo
        self._modelo = TextEmbedding(modelo, cache_dir=str(CACHE_MODELOS))

    def embed_documents(self, textos: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._modelo.embed(textos)]

    def embed_query(self, texto: str) -> list[float]:
        return self.embed_documents([texto])[0]


_embeddings: Optional[EmbeddingsLocales] = None


def obtener_embeddings() -> EmbeddingsLocales:
    """El modelo tarda unos segundos en cargar: se carga una vez y se reutiliza."""
    global _embeddings
    if _embeddings is None:
        _embeddings = EmbeddingsLocales()
    return _embeddings


# ── OFFLINE: del corpus al índice ─────────────────────────────────────────────

def cargar_corpus(ruta: Path = RUTA_CORPUS) -> list[Document]:
    """
    Cada documento del JSON pasa a ser un Document de LangChain:
        page_content → título + descripcion_semantica   (lo que se convierte en embedding)
        metadata     → id, título y metadatos            (lo que se filtra de forma exacta)
    Cada documento ya es una unidad de sentido: no hace falta dividirlo en fragmentos.
    """
    corpus = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return [
        Document(
            id=doc["id"],
            page_content=f"{doc['titulo']}. {doc['descripcion_semantica']}",
            metadata={"id": doc["id"], "titulo": doc["titulo"], **doc["metadatos"]},
        )
        for doc in corpus
    ]


def huella(ruta: Path = RUTA_CORPUS, modelo: str = MODELO_EMBEDDINGS) -> str:
    """Si cambia el corpus o el modelo, cambia la huella y hay que volver a indexar."""
    return hashlib.sha256(Path(ruta).read_bytes() + modelo.encode()).hexdigest()[:16]


def _cliente(carpeta: Path) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(carpeta), settings=Settings(anonymized_telemetry=False))


def indexar(ruta: Path = RUTA_CORPUS, carpeta: Path = CARPETA_INDICE,
            embeddings: Optional[Embeddings] = None) -> Chroma:
    """Paso OFFLINE: calcula el embedding de cada documento y lo guarda en Chroma (similitud coseno)."""
    embeddings = embeddings or obtener_embeddings()
    modelo = getattr(embeddings, "modelo", MODELO_EMBEDDINGS)
    cliente = _cliente(carpeta)
    try:
        cliente.delete_collection(COLECCION)
    except Exception:
        pass   # todavía no existía
    base = Chroma(
        client=cliente,
        collection_name=COLECCION,
        embedding_function=embeddings,
        collection_metadata={"hnsw:space": "cosine", "huella": huella(ruta, modelo)},
    )
    base.add_documents(cargar_corpus(ruta))
    return base


def abrir(ruta: Path = RUTA_CORPUS, carpeta: Path = CARPETA_INDICE,
          embeddings: Optional[Embeddings] = None, avisar=print) -> Chroma:
    """Abre el índice guardado. Si no existe o el corpus cambió (otra huella), lo reindexa."""
    embeddings = embeddings or obtener_embeddings()
    modelo = getattr(embeddings, "modelo", MODELO_EMBEDDINGS)
    try:
        coleccion = _cliente(carpeta).get_collection(COLECCION)
        if (coleccion.metadata or {}).get("huella") == huella(ruta, modelo):
            return Chroma(client=_cliente(carpeta), collection_name=COLECCION, embedding_function=embeddings)
    except Exception:
        pass   # no existe todavía
    if avisar:
        avisar("  ⚙️  Indexando el corpus (paso OFFLINE: se hace una vez y queda en entrega_3/indice_chroma/)...")
    return indexar(ruta, carpeta, embeddings)


# ── ONLINE: buscar ────────────────────────────────────────────────────────────

@dataclass
class Recuperado:
    """Un documento recuperado, con lo que necesitan la cadena, el guardrail y la traza."""
    id: str
    titulo: str
    texto: str
    metadatos: dict
    similitud: float
    supera_umbral: bool


def armar_filtro(filtro: Optional[dict]) -> Optional[dict]:
    """Chroma pide `$and` para combinar más de una condición."""
    if not filtro:
        return None
    if len(filtro) == 1:
        return dict(filtro)
    return {"$and": [{clave: valor} for clave, valor in filtro.items()]}


def buscar(base: Chroma, pregunta: str, k: int = K, filtro: Optional[dict] = SOLO_VIGENTES,
           umbral: float = UMBRAL_SIMILITUD) -> list[Recuperado]:
    """
    Los k documentos más parecidos a la pregunta, de mayor a menor similitud.
    `filtro` es la parte exacta del filtrado híbrido (por defecto, solo vigentes); `None` lo desactiva.
    La similitud es el coseno entre los vectores (1 = mismo significado): Chroma devuelve la
    distancia coseno (1 - coseno), así que similitud = 1 - distancia, acotada a [0, 1] porque
    dos textos sin relación pueden dar un coseno apenas negativo.
    """
    resultados = base.similarity_search_with_score(pregunta, k=k, filter=armar_filtro(filtro))
    recuperados = []
    for doc, distancia in resultados:
        similitud = round(min(max(1.0 - float(distancia), 0.0), 1.0), 4)
        recuperados.append(Recuperado(
            id=doc.metadata["id"],
            titulo=doc.metadata["titulo"],
            texto=doc.page_content,
            metadatos={c: v for c, v in doc.metadata.items() if c not in ("id", "titulo")},
            similitud=similitud,
            supera_umbral=similitud >= umbral,
        ))
    return sorted(recuperados, key=lambda r: r.similitud, reverse=True)
