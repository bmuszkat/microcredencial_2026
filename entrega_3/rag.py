"""
RAG de la clínica (Entrega 3, Parte B). Por ahora, la consola de la base de conocimiento:

    python entrega_3/rag.py indexar                 # fuerza la reindexación (la primera vez baja el modelo)
    python entrega_3/rag.py ver                     # qué quedó guardado en Chroma
    python entrega_3/rag.py buscar "pregunta"       # los k documentos más parecidos (solo vigentes)
    python entrega_3/rag.py buscar "pregunta" --todas   # lo mismo sin el filtro de vigencia

La búsqueda no usa API key: los embeddings se calculan en la compu (ver base_conocimiento.py).
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

ENTREGA_3 = Path(__file__).resolve().parent
sys.path.insert(0, str(ENTREGA_3))

import base_conocimiento as bc  # noqa: E402


# ── Consola ───────────────────────────────────────────────────────────────────

def cmd_indexar(args) -> int:
    print(f"Indexando {bc.RUTA_CORPUS.relative_to(ENTREGA_3.parent)} con {bc.MODELO_EMBEDDINGS}...")
    base = bc.indexar()
    print(f"Listo: {len(base.get()['ids'])} documentos en {bc.CARPETA_INDICE.relative_to(ENTREGA_3.parent)}/")
    return 0


def cmd_ver(args) -> int:
    """Lo que guarda Chroma por documento: id, metadatos, texto y vector."""
    base = bc.abrir()
    guardado = base.get(include=["embeddings", "documents", "metadatas"])
    print(f"Colección '{bc.COLECCION}': {len(guardado['ids'])} documentos · modelo {bc.MODELO_EMBEDDINGS}\n")
    filas = sorted(zip(guardado["ids"], guardado["metadatas"], guardado["documents"], guardado["embeddings"]))
    for id_, metadatos, texto, vector in filas:
        extra = {c: metadatos[c] for c in sorted(metadatos) if c not in ("id", "titulo")}
        print(f"[{id_}]  {'vigente' if metadatos['vigente'] else 'DEROGADO'}")
        print(f"   metadatos: {extra}")
        print(f"   texto:     {texto[:90]}...")
        print(f"   vector:    {len(vector)} números [{', '.join(f'{x:.3f}' for x in vector[:3])}, ...]\n")
    return 0


def imprimir_recuperados(recuperados: list[bc.Recuperado], umbral: float = bc.UMBRAL_SIMILITUD) -> None:
    print(f"   {'similitud':>9}  {'':1}  documento")
    for r in recuperados:
        marca = "✓" if r.supera_umbral else "·"
        estado = "" if r.metadatos.get("vigente", True) else "  (DEROGADO)"
        print(f"   {r.similitud:>9.3f}  {marca}  {r.id}{estado}")
    print(f"   ✓ supera el umbral de similitud ({umbral:g}) · no lo supera")


def cmd_buscar(args) -> int:
    pregunta = " ".join(args.pregunta)
    filtro: Optional[dict] = None if args.todas else bc.SOLO_VIGENTES
    base = bc.abrir()
    print(f"Pregunta: {pregunta}")
    print(f"Filtro:   {filtro if filtro else 'ninguno (incluye documentos derogados)'} · k={args.k}\n")
    imprimir_recuperados(bc.buscar(base, pregunta, k=args.k, filtro=filtro))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # la consola de Windows no siempre usa UTF-8
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="RAG de la Entrega 3 (Parte B)")
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("indexar", help="reindexa el corpus (la primera vez baja el modelo, unos 640 MB)")
    sub.add_parser("ver", help="muestra lo que guarda Chroma: ids, metadatos, texto y vector")
    p_buscar = sub.add_parser("buscar", help="los k documentos más parecidos a una pregunta")
    p_buscar.add_argument("pregunta", nargs="+")
    p_buscar.add_argument("--todas", action="store_true", help="sin el filtro de vigencia (muestra los derogados)")
    p_buscar.add_argument("-k", type=int, default=bc.K, help=f"cuántos documentos recuperar (por defecto {bc.K})")

    args = parser.parse_args(argv)
    comandos = {"indexar": cmd_indexar, "ver": cmd_ver, "buscar": cmd_buscar}
    return comandos[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
