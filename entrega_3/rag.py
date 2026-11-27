"""
RAG de la clínica (Entrega 3, Parte B). Por ahora, la consola de la base de conocimiento:

    python entrega_3/rag.py indexar                 # fuerza la reindexación (la primera vez baja el modelo)
    python entrega_3/rag.py ver                     # qué quedó guardado en Chroma
    python entrega_3/rag.py buscar "pregunta"       # los k documentos más parecidos (solo vigentes)
    python entrega_3/rag.py buscar "pregunta" --todas   # lo mismo sin el filtro de vigencia
    python entrega_3/rag.py calibrar                # similitud de las preguntas de calibración (umbral)
    python entrega_3/rag.py calibrar --guardar      # lo mismo, y lo guarda en entrega_3/evidencia/

La búsqueda no usa API key: los embeddings se calculan en la compu (ver base_conocimiento.py).
"""

import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from typing import Optional

ENTREGA_3 = Path(__file__).resolve().parent
sys.path.insert(0, str(ENTREGA_3))

import base_conocimiento as bc  # noqa: E402

RUTA_CALIBRACION = ENTREGA_3 / "datos" / "preguntas_calibracion.json"
CARPETA_EVIDENCIA = ENTREGA_3 / "evidencia"


# ── Calibración del umbral (design D6) ────────────────────────────────────────

def medir_calibracion(base, preguntas: list[dict]) -> list[dict]:
    """Para cada pregunta: el mejor documento, su similitud y en qué posición quedó el esperado."""
    filas = []
    for p in preguntas:
        recuperados = bc.buscar(base, p["pregunta"], k=bc.K, umbral=0.0)
        ids = [r.id for r in recuperados]
        filas.append({
            **p,
            "mejor": ids[0],
            "similitud": recuperados[0].similitud,
            "posicion_esperado": ids.index(p["documento_esperado"]) + 1 if p["documento_esperado"] in ids else None,
        })
    return filas


def errores_por_umbral(filas: list[dict], umbral: float) -> dict:
    """Cuántas preguntas clasifica mal un umbral: 'dentro' rechazadas y 'fuera' aceptadas."""
    dentro_rechazadas = [f["id"] for f in filas if f["tipo"] == "dentro" and f["similitud"] < umbral]
    fuera_aceptadas = [f["id"] for f in filas if f["tipo"] == "fuera" and f["similitud"] >= umbral]
    return {"umbral": umbral, "dentro_rechazadas": dentro_rechazadas, "fuera_aceptadas": fuera_aceptadas,
            "errores": len(dentro_rechazadas) + len(fuera_aceptadas)}


def imprimir_calibracion(filas: list[dict]) -> None:
    for tipo, titulo in (("dentro", "DENTRO del corpus (debería superar el umbral)"),
                         ("fuera", "FUERA del corpus (no debería superarlo)")):
        print(titulo)
        print(f"   {'id':<4} {'similitud':>9}  {'mejor documento':<22} {'esperado':>8}  pregunta")
        for f in sorted((f for f in filas if f["tipo"] == tipo), key=lambda f: -f["similitud"]):
            if tipo == "dentro":
                posicion = f"#{f['posicion_esperado']}" if f["posicion_esperado"] else "no está"
            else:
                posicion = "—"
            print(f"   {f['id']:<4} {f['similitud']:>9.3f}  {f['mejor']:<22} {posicion:>8}  {f['pregunta']}")
        similitudes = [f["similitud"] for f in filas if f["tipo"] == tipo]
        print(f"   rango: {min(similitudes):.3f} a {max(similitudes):.3f}\n")

    dentro = [f for f in filas if f["tipo"] == "dentro"]
    primero = sum(f["posicion_esperado"] == 1 for f in dentro)
    print(f"Recuperación: el documento esperado sale primero en {primero}/{len(dentro)} preguntas 'dentro'.\n")

    print("Errores por umbral (dentro rechazadas + fuera aceptadas):")
    for centesimos in range(30, 61, 2):
        e = errores_por_umbral(filas, centesimos / 100)
        detalle = ", ".join(e["dentro_rechazadas"] + e["fuera_aceptadas"]) or "ninguno"
        print(f"   {e['umbral']:.2f}  {e['errores']:>2} errores   ({detalle})")
    e = errores_por_umbral(filas, bc.UMBRAL_SIMILITUD)
    detalle = ", ".join(e["dentro_rechazadas"] + e["fuera_aceptadas"]) or "ninguno"
    print(f"\nUmbral vigente en base_conocimiento.py: {bc.UMBRAL_SIMILITUD:g} → {e['errores']} errores ({detalle})")


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


def cmd_calibrar(args) -> int:
    preguntas = json.loads(RUTA_CALIBRACION.read_text(encoding="utf-8"))["preguntas"]
    salida = io.StringIO()
    with redirect_stdout(salida):
        print(f"Calibración del umbral · {date.today().isoformat()} · modelo {bc.MODELO_EMBEDDINGS} · "
              f"k={bc.K} · filtro {bc.SOLO_VIGENTES}")
        print(f"Preguntas: {RUTA_CALIBRACION.relative_to(ENTREGA_3.parent)} (fijadas antes de medir)\n")
        imprimir_calibracion(medir_calibracion(bc.abrir(), preguntas))
    print(salida.getvalue(), end="")
    if args.guardar:
        CARPETA_EVIDENCIA.mkdir(exist_ok=True)
        ruta = CARPETA_EVIDENCIA / f"calibracion_{date.today().isoformat()}.txt"
        ruta.write_text(salida.getvalue(), encoding="utf-8")
        print(f"\nGuardado en {ruta.relative_to(ENTREGA_3.parent)}")
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

    p_calibrar = sub.add_parser("calibrar", help="similitud de las preguntas de calibración y errores por umbral")
    p_calibrar.add_argument("--guardar", action="store_true", help="guardar la tabla en entrega_3/evidencia/")

    args = parser.parse_args(argv)
    comandos = {"indexar": cmd_indexar, "ver": cmd_ver, "buscar": cmd_buscar, "calibrar": cmd_calibrar}
    return comandos[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
