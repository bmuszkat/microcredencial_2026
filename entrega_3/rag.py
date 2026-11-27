"""
RAG de la clínica (Entrega 3, Parte B), armado como una CADENA de LangChain (LCEL):

    pregunta ──┬──────────────────────────────────────────────────────┐
               └─▶ recuperar (embedding + Chroma + filtro vigente + umbral) ┤
                                                                      ▼
               ¿algún documento supera el umbral?
                 ├─ NO → "No tengo información oficial sobre esa consulta."   (el LLM ni se llama)
                 └─ SÍ → plantilla(documentos con [ID] + pregunta) | modelo | parser → respuesta con citas

Es la misma idea de la Clase 4 (plantilla | modelo | parser) con un paso nuevo adelante: RECUPERAR
el contexto. Sin API key el "modelo" es una simulación que devuelve el primer documento recuperado;
la recuperación corre de verdad igual.

Consola:

    python entrega_3/rag.py indexar                 # fuerza la reindexación (la primera vez baja el modelo)
    python entrega_3/rag.py ver                     # qué quedó guardado en Chroma
    python entrega_3/rag.py buscar "pregunta"       # los k documentos más parecidos (solo vigentes)
    python entrega_3/rag.py buscar "pregunta" --todas   # lo mismo sin el filtro de vigencia
    python entrega_3/rag.py preguntar "pregunta"    # respuesta completa: recuperación + LLM + guardrail
    python entrega_3/rag.py preguntar "pregunta" --simulacion   # lo mismo sin llamar al LLM
    python entrega_3/rag.py comparar                # comparación B.3: sin grounding vs. con RAG (--simulacion, --guardar)
    python entrega_3/rag.py calibrar                # similitud de las preguntas de calibración (umbral)
    python entrega_3/rag.py calibrar --guardar      # lo mismo, y lo guarda en entrega_3/evidencia/

La búsqueda no usa API key: los embeddings se calculan en la compu (ver base_conocimiento.py).
"""

import argparse
import io
import json
import re
import sys
import time
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

ENTREGA_3 = Path(__file__).resolve().parent
sys.path.insert(0, str(ENTREGA_3.parent / "entrega_2"))   # se reusa clinica/ (config del proveedor) sin moverlo
sys.path.insert(0, str(ENTREGA_3))

from langchain_core.output_parsers import StrOutputParser  # noqa: E402
from langchain_core.prompt_values import ChatPromptValue  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402
from langchain_core.runnables import (RunnableBranch, RunnableLambda, RunnableParallel,  # noqa: E402
                                      RunnablePassthrough)

import base_conocimiento as bc  # noqa: E402
from clinica.config import detectar_proveedor, modelo_de  # noqa: E402
from redactor import valores_del_texto  # noqa: E402   (la misma lectura de montos que el guardrail de la Parte A)

RUTA_CALIBRACION = ENTREGA_3 / "datos" / "preguntas_calibracion.json"
RUTA_COMPARACION = ENTREGA_3 / "datos" / "preguntas_comparacion.json"
PAUSA_POR_DEFECTO = 20   # segundos entre llamadas: límite gratuito de Groq
CARPETA_EVIDENCIA = ENTREGA_3 / "evidencia"
CARPETA_PROMPTS = ENTREGA_3 / "prompts"

SIN_INFORMACION = "No tengo información oficial sobre esa consulta."
URL_GROQ = "https://api.groq.com/openai/v1"


# ── 1) Plantillas ─────────────────────────────────────────────────────────────

def leer_prompt(nombre: str) -> str:
    return (CARPETA_PROMPTS / f"{nombre}.txt").read_text(encoding="utf-8")


PLANTILLA_RAG = ChatPromptTemplate.from_messages([
    ("system", leer_prompt("rag_v1")),
    ("human", "Documentos recuperados del corpus de la clínica:\n{contexto}\n\n"
              "Consulta del paciente:\n<consulta>\n{pregunta}\n</consulta>"),
])

# Para la comparación B.3: la misma pregunta SIN contexto, como el modelo de la Entrega 1
PLANTILLA_SIN_GROUNDING = ChatPromptTemplate.from_messages([
    ("system", leer_prompt("sin_grounding_v1")),
    ("human", "{pregunta}"),
])


def formatear_contexto(recuperados: list[bc.Recuperado]) -> str:
    """Solo los documentos que superan el umbral, cada uno con su id adelante para poder citarlo."""
    return "\n\n".join(f"[{r.id}] {r.texto}" for r in recuperados if r.supera_umbral)


def hay_contexto(recuperados: list[bc.Recuperado]) -> bool:
    return any(r.supera_umbral for r in recuperados)


# ── 2) Modelo: el real si hay key; si no, una simulación ──────────────────────

def _modelo_simulado(prompt: ChatPromptValue) -> str:
    """Sin API key: devuelve el texto del primer documento recuperado, tal cual y con su cita. No redacta nada."""
    for linea in prompt.messages[-1].content.splitlines():
        if linea.startswith("["):                                   # "[DOC-TURNO] Qué llevar el día del turno. ..."
            id_, texto = linea[1:].split("] ", 1)
            cuerpo = texto.split(". ", 1)[-1]                        # sin el título
            cuerpo = cuerpo.split(" Responde a", 1)[0]               # sin las preguntas de ejemplo
            return f"Según la información oficial de la clínica ({id_}): {cuerpo}"
    return SIN_INFORMACION


modelo_simulado = RunnableLambda(_modelo_simulado)


def crear_modelo(temperatura: float = 0):
    """
    Devuelve (modelo, origen). Cualquier chat model de LangChain encaja en la cadena.
    Groq y OpenAI usan el mismo formato, así que alcanza con ChatOpenAI (design D7).
    Sin key, o con un proveedor que el RAG no soporta, usa la simulación.
    """
    proveedor = detectar_proveedor()
    if proveedor is None:
        return modelo_simulado, "SIMULACIÓN (sin API key)"
    nombre, key = proveedor
    if nombre not in ("groq", "openai"):
        return modelo_simulado, f"SIMULACIÓN (el RAG solo usa Groq u OpenAI; el .env tiene {nombre})"
    from langchain_openai import ChatOpenAI
    modelo = ChatOpenAI(model=modelo_de(nombre), temperature=temperatura, api_key=key, max_retries=3,
                        base_url=URL_GROQ if nombre == "groq" else None)
    return modelo, f"{nombre} ({modelo_de(nombre)})"


# ── 3) La cadena completa ─────────────────────────────────────────────────────

def crear_cadena(buscador, modelo):
    """
    `buscador`: pregunta → list[Recuperado] (la "R" del RAG). `modelo`: cualquier Runnable de chat.
    Devuelve un dict con la pregunta, los documentos recuperados y la respuesta.
    """
    generar = RunnableBranch(
        (lambda x: not hay_contexto(x["documentos"]), RunnableLambda(lambda x: SIN_INFORMACION)),   # ✋ umbral
        RunnablePassthrough.assign(contexto=lambda x: formatear_contexto(x["documentos"]))
        | PLANTILLA_RAG | modelo | StrOutputParser(),
    )
    return RunnableParallel(pregunta=RunnablePassthrough(), documentos=RunnableLambda(buscador)).assign(respuesta=generar)


def buscador_de(base, filtro: Optional[dict] = bc.SOLO_VIGENTES, umbral: float = bc.UMBRAL_SIMILITUD):
    """El paso de recuperación sobre el índice de Chroma, con el filtro híbrido y el umbral calibrado."""
    return lambda pregunta: bc.buscar(base, pregunta, filtro=filtro, umbral=umbral)


def cadena_sin_grounding(modelo):
    return PLANTILLA_SIN_GROUNDING | modelo | StrOutputParser()


# ── 4) Guardrail en código (design D9) ────────────────────────────────────────
# El prompt PIDE citar y no inventar; el código lo VERIFICA. Es la misma idea del paso 11 de la Parte A:
# lo que llega al paciente tiene que tener respaldo en lo que se recuperó.

RESPONDIDA, SIN_INFORMACION_OFICIAL, NO_VERIFICADO, ERROR = "respondida", "sin_informacion", "no_verificado", "error"

_CITA = re.compile(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b")              # CAR-CANCELACION-V2, DOC-TURNO
_PORCENTAJE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def _montos(texto: str) -> set[int]:
    return {valor for _, valor in valores_del_texto(texto)[0]}


def _porcentajes(texto: str) -> set[str]:
    return {m.group(1).replace(",", ".") for m in _PORCENTAJE.finditer(texto)}


def citas_del_texto(texto: str) -> list[str]:
    return list(dict.fromkeys(_CITA.findall(texto)))   # sin repetir, en orden de aparición


def verificar_respuesta(texto: str, recuperados: list[bc.Recuperado]) -> tuple[str, list[str], list[str]]:
    """
    Devuelve (estado, citas, problemas). La respuesta se acepta solo si:
      1. cita al menos un documento, y todos los citados están entre los que superaron el umbral;
      2. cada monto y cada porcentaje del texto aparece en alguno de esos documentos.
    Si el modelo respondió el fallback, no hay nada que verificar: no tenía información.
    """
    texto = texto.strip()
    if texto.startswith(SIN_INFORMACION):
        return SIN_INFORMACION_OFICIAL, [], []

    usables = [r for r in recuperados if r.supera_umbral]
    ids_usables = {r.id for r in usables}
    texto_usables = " ".join(r.texto for r in usables)
    citas = citas_del_texto(texto)
    problemas = []
    if not citas:
        problemas.append("la respuesta no cita ningún documento")
    problemas += [f"cita un documento que no se recuperó: {c}" for c in citas if c not in ids_usables]
    problemas += [f"monto sin respaldo en los documentos: ${m:,}".replace(",", ".")
                  for m in sorted(_montos(texto) - _montos(texto_usables))]
    problemas += [f"porcentaje sin respaldo en los documentos: {p} %"
                  for p in sorted(_porcentajes(texto) - _porcentajes(texto_usables))]
    return (NO_VERIFICADO if problemas else RESPONDIDA), citas, problemas


# ── 5) El resultado que usan la consola y el workflow (design D10) ────────────

@dataclass
class ResultadoRag:
    estado: str                         # respondida · sin_informacion · no_verificado · error
    texto: Optional[str]                # lo que se le puede mostrar al paciente (None si no hay)
    citas: list[str] = field(default_factory=list)
    candidatos: list[tuple[str, float, bool]] = field(default_factory=list)   # (id, similitud, supera umbral)
    llamo_llm: bool = False
    detalle: Optional[str] = None       # por qué no se verificó o qué error hubo (para la traza, no para el paciente)
    origen: str = ""
    texto_generado: Optional[str] = None   # lo que escribió el modelo, aunque se haya descartado


def ocultar_org(texto: str) -> str:
    """Los errores 429 de Groq traen el id de la organización: no se guarda en la evidencia."""
    return re.sub(r"org_[A-Za-z0-9]+", "org_[OCULTO]", texto)


def responder(pregunta: str, cadena, origen: str = "") -> ResultadoRag:
    """Corre la cadena y aplica el guardrail. Nunca inventa: si algo falla, no hay texto."""
    try:
        r = cadena.invoke(pregunta)
    except Exception as e:   # la API falló después de los reintentos: no inventamos, queda para una persona
        return ResultadoRag(ERROR, None, detalle=ocultar_org(f"{type(e).__name__}: {e}"), llamo_llm=True, origen=origen)

    candidatos = [(d.id, d.similitud, d.supera_umbral) for d in r["documentos"]]
    if not hay_contexto(r["documentos"]):
        return ResultadoRag(SIN_INFORMACION_OFICIAL, SIN_INFORMACION, candidatos=candidatos,
                            detalle="ningún documento supera el umbral: el LLM no se llamó", origen=origen)

    estado, citas, problemas = verificar_respuesta(r["respuesta"], r["documentos"])
    if estado == NO_VERIFICADO:
        return ResultadoRag(estado, None, citas, candidatos, True, "; ".join(problemas), origen, r["respuesta"])
    return ResultadoRag(estado, r["respuesta"].strip(), citas, candidatos, True,
                        "el modelo respondió que no tiene la información" if estado == SIN_INFORMACION_OFICIAL else None,
                        origen, r["respuesta"])


def crear_respondedor(base=None, modelo=None, origen: Optional[str] = None):
    """Arma el RAG completo (índice, filtro, umbral y modelo del .env) y devuelve pregunta → ResultadoRag."""
    base = base if base is not None else bc.abrir()
    if modelo is None:
        modelo, origen = crear_modelo()
    cadena = crear_cadena(buscador_de(base), modelo)
    return lambda pregunta: responder(pregunta, cadena, origen or "")


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


def ruta_corta(ruta: Path) -> str:
    """La ruta relativa a la raíz del repo, o completa si está afuera (por ejemplo, en los tests)."""
    try:
        return str(ruta.relative_to(ENTREGA_3.parent))
    except ValueError:
        return str(ruta)


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


def imprimir_resultado(r: ResultadoRag) -> None:
    print("Recuperación:")
    for id_, similitud, supera in r.candidatos:
        print(f"   {similitud:>9.3f}  {'✓' if supera else '·'}  {id_}")
    print(f"Estado:    {r.estado}{'' if r.llamo_llm else '  (el LLM no se llamó)'}")
    if r.citas:
        print(f"Citas:     {', '.join(r.citas)}")
    if r.detalle:
        print(f"Detalle:   {r.detalle}")
    if r.texto:
        print(f"Respuesta: {r.texto}")
    elif r.texto_generado:
        print(f"Descartada por el guardrail: {r.texto_generado}")


def cmd_preguntar(args) -> int:
    pregunta = " ".join(args.pregunta)
    modelo, origen = (modelo_simulado, "SIMULACIÓN (--simulacion)") if args.simulacion else crear_modelo()
    print(f"Pregunta:  {pregunta}")
    print(f"Modelo:    {origen} · umbral {bc.UMBRAL_SIMILITUD:g} · k={bc.K} · filtro {bc.SOLO_VIGENTES}\n")
    imprimir_resultado(crear_respondedor(modelo=modelo, origen=origen)(pregunta))
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
        print(f"\nGuardado en {ruta_corta(ruta)}")
    return 0


# ── Comparación B.3: sin grounding vs. con RAG (design D14) ───────────────────

def evaluar_esperado(r: ResultadoRag, esperado: dict) -> list[str]:
    """Compara el resultado del RAG con lo esperado (fijado antes de correr). Devuelve lo que no se cumplió."""
    fallas = []
    if r.estado != esperado["estado"]:
        fallas.append(f"estado {r.estado}, se esperaba {esperado['estado']}")
    if esperado["documento"] and esperado["documento"] not in r.citas:
        fallas.append(f"no cita {esperado['documento']}")
    texto = (r.texto or "").lower()
    if esperado["debe_contener"] and not any(t.lower() in texto for t in esperado["debe_contener"]):
        fallas.append(f"no menciona ninguno de: {', '.join(esperado['debe_contener'])}")
    fallas += [f"menciona «{t}»" for t in esperado["no_debe_contener"] if t.lower() in texto]
    return fallas


class Pausa:
    """Espera `segundos` antes de cada llamada al LLM salvo la primera (límite gratuito de Groq)."""

    def __init__(self, segundos: float):
        self.segundos, self.llamadas = segundos, 0

    def __call__(self, entrada):
        if self.llamadas and self.segundos:
            time.sleep(self.segundos)
        self.llamadas += 1
        return entrada


def correr_comparacion(preguntas: list[dict], responder_rag, responder_sin_grounding) -> int:
    """Imprime cada pregunta con las dos respuestas lado a lado y devuelve cuántas dieron lo esperado con RAG."""
    aciertos = 0
    for p in preguntas:
        print(f"━━━ {p['id']} · {p['pregunta']}")
        for e in p["entrega_1"]:
            print(f"  Entrega 1, sin datos ({e['archivo']}):\n     «{e['cita']}»")
        print(f"  SIN GROUNDING:\n     {responder_sin_grounding(p)}")
        r = responder_rag(p["pregunta"])
        print("  CON RAG:")
        print("     recuperados: " + " · ".join(f"{i} {s:.3f}{' ✓' if ok else ''}" for i, s, ok in r.candidatos))
        print(f"     estado: {r.estado}{'' if r.llamo_llm else ' (el LLM no se llamó)'}"
              + (f" · citas: {', '.join(r.citas)}" if r.citas else ""))
        if r.detalle:
            print(f"     detalle: {r.detalle}")
        print(f"     {r.texto if r.texto else '(sin texto para el paciente)'}")
        if r.texto is None and r.texto_generado:
            print(f"     descartada por el guardrail: {r.texto_generado}")
        fallas = evaluar_esperado(r, p["esperado_rag"])
        aciertos += not fallas
        print(f"  Esperado con RAG: {'✓ cumple' if not fallas else '✗ ' + '; '.join(fallas)}\n")
    print(f"Resultado: {aciertos}/{len(preguntas)} preguntas con lo esperado con RAG")
    return aciertos


class _Duplicar(io.TextIOBase):
    """Escribe en la consola y en un buffer a la vez: se ve en vivo y después se guarda."""

    def __init__(self, consola):
        self.consola, self.buffer = consola, io.StringIO()

    def write(self, texto):
        self.consola.write(texto)
        self.consola.flush()
        return self.buffer.write(texto)


def cmd_comparar(args) -> int:
    preguntas = json.loads(RUTA_COMPARACION.read_text(encoding="utf-8"))["preguntas"]
    if args.simulacion:
        modelo, origen = modelo_simulado, "SIMULACIÓN (--simulacion)"
    else:
        modelo, origen = crear_modelo()
    simulado = modelo is modelo_simulado
    pausa = 0 if simulado else args.pausa
    pausado = RunnableLambda(Pausa(pausa)) | modelo

    def sin_grounding(p: dict) -> str:
        if simulado:   # sin LLM real no hay "memoria" que mostrar: se usa la respuesta de ejemplo
            return f"(simulación) {p['simulacion_sin_grounding']}"
        try:
            return cadena_sin_grounding(pausado).invoke({"pregunta": p["pregunta"]}).strip()
        except Exception as e:
            return ocultar_org(f"(falló la API: {type(e).__name__}: {e})")

    salida = _Duplicar(sys.stdout)
    with redirect_stdout(salida):
        print(f"Comparación B.3 · {date.today().isoformat()} · modelo {origen} · prompts sin_grounding_v1 y rag_v1")
        print(f"RAG: k={bc.K} · filtro {bc.SOLO_VIGENTES} · umbral {bc.UMBRAL_SIMILITUD:g} · "
              f"pausa {pausa:g} s entre llamadas")
        print(f"Preguntas: {RUTA_COMPARACION.relative_to(ENTREGA_3.parent)} (fijadas antes de correr)\n")
        correr_comparacion(preguntas, crear_respondedor(modelo=pausado, origen=origen), sin_grounding)
    if args.guardar:
        CARPETA_EVIDENCIA.mkdir(exist_ok=True)
        nombre = "simulacion" if simulado else origen.split(" ")[0]
        ruta = CARPETA_EVIDENCIA / f"comparacion_{nombre}_{date.today().isoformat()}.txt"
        ruta.write_text(ocultar_org(salida.buffer.getvalue()), encoding="utf-8")
        print(f"\nGuardado en {ruta_corta(ruta)}")
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

    p_preguntar = sub.add_parser("preguntar", help="respuesta completa del RAG: recuperación, LLM y guardrail")
    p_preguntar.add_argument("pregunta", nargs="+")
    p_preguntar.add_argument("--simulacion", action="store_true", help="sin llamar al LLM, aunque haya key")
    p_comparar = sub.add_parser("comparar", help="comparación B.3: sin grounding vs. con RAG")
    p_comparar.add_argument("--simulacion", action="store_true", help="sin llamar al LLM, aunque haya key")
    p_comparar.add_argument("--pausa", type=float, default=PAUSA_POR_DEFECTO, help="segundos entre llamadas al LLM")
    p_comparar.add_argument("--guardar", action="store_true", help="guardar la salida en entrega_3/evidencia/")
    p_calibrar = sub.add_parser("calibrar", help="similitud de las preguntas de calibración y errores por umbral")
    p_calibrar.add_argument("--guardar", action="store_true", help="guardar la tabla en entrega_3/evidencia/")

    args = parser.parse_args(argv)
    comandos = {"indexar": cmd_indexar, "ver": cmd_ver, "buscar": cmd_buscar, "preguntar": cmd_preguntar,
                "calibrar": cmd_calibrar, "comparar": cmd_comparar}
    return comandos[args.comando](args)


if __name__ == "__main__":
    sys.exit(main())
