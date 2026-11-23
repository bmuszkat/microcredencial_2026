"""
Evaluación de la extracción sobre el set de 50 mensajes etiquetados (spec `evaluacion-extraccion`)
=================================================================================================
Pone a prueba la hipótesis más riesgosa de la Entrega 1 (B.5): que el modelo extraiga bien la
intención y los datos de al menos el 90 % de los mensajes.

Para cada mensaje de datos/set_evaluacion.json corre el mismo flujo que app.py y compara contra la
respuesta esperada, que se escribió ANTES de correr. Informa:
  - % de respuestas con JSON válido
  - % que cumplen el contrato
  - % de mensajes con las intenciones exactas (el orden no importa)
  - % de entidades correctas (dni, profesional, fechas, estudio)
  - % de mensajes completamente correctos (intenciones + las 5 entidades)  ← hipótesis B.5

Uso (desde la raíz del repo):
    python entrega_2/evaluar.py              → prompt vigente (v2)
    python entrega_2/evaluar.py v1           → otra versión, para comparar
    python entrega_2/evaluar.py v2 --pausa 30 --desde-cero
    python entrega_2/evaluar.py v2 --limite 3     → solo los primeros 3 mensajes (prueba rápida)

Cada resultado se guarda apenas llega en evidencia/evaluacion_<version>.json: si la corrida se
corta (o la API pone límites), al volver a ejecutar retoma donde quedó.
"""

import argparse
import json
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from clinica.config import RAIZ_ENTREGA, ConfiguracionError, detectar_proveedor
from clinica.contrato import ExtraccionPacienteV1, contrato_para
from clinica.extractor import PROMPT_VERSION, procesar_mensaje

ENTIDADES = ("dni", "profesional", "fecha_turno_actual", "fecha_deseada", "estudio")
RUTA_SET = RAIZ_ENTREGA / "datos" / "set_evaluacion.json"
PAUSA_POR_DEFECTO = 20  # segundos entre llamadas: el límite gratuito de Groq admite ~3 por minuto


# ── Comparación ────────────────────────────────────────────────────────────────

def _normalizar_texto(valor: str) -> str:
    """Minúsculas y sin tildes: "Miércoles" → "miercoles"."""
    sin_tildes = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode("ascii")
    return " ".join(sin_tildes.lower().split())


def intenciones_correctas(esperadas: list[str], obtenidas: list[str]) -> bool:
    """El orden no importa: ["a", "b"] == ["b", "a"]."""
    return set(esperadas) == set(obtenidas)


def entidad_correcta(nombre: str, esperado: Optional[str], obtenido: Optional[str]) -> bool:
    """
    null esperado → el modelo tiene que devolver null.
    DNI → igualdad exacta.
    Resto → el valor del modelo tiene que contener la palabra clave esperada
            ("jueves a las 15 hs" contiene "jueves"), sin distinguir mayúsculas ni tildes.
    """
    if obtenido is not None and not str(obtenido).strip():
        obtenido = None
    if esperado is None:
        return obtenido is None
    if obtenido is None:
        return False
    if nombre == "dni":
        return obtenido == esperado
    return _normalizar_texto(esperado) in _normalizar_texto(str(obtenido))


def normalizar_v1(extraccion: dict) -> dict:
    """
    Traduce una extracción del contrato v1 al espacio de intenciones vigente:
    `otra` + es_consulta_medica=true  ≡  `consulta_medica` (y si no había `otra`, se agrega).
    """
    datos = dict(extraccion)
    es_medica = datos.pop("es_consulta_medica", False)
    intenciones = list(datos["intenciones"])
    if es_medica:
        intenciones = [i for i in intenciones if i != "otra"]
        if "consulta_medica" not in intenciones:
            intenciones.append("consulta_medica")
    datos["intenciones"] = intenciones
    return datos


# ── Evaluación de un caso ───────────────────────────────────────────────────────

def extraccion_evaluable(resultado: dict, version: str) -> Optional[dict]:
    """
    La extracción a comparar, o None si el mensaje no llegó a una extracción válida
    (COMUNICACION, FORMATO o CONTRATO). Un error de REGLA NO descuenta: el modelo extrajo bien
    lo que dijo el paciente, aunque el dato no sirva para el negocio (design D6).
    """
    extraccion = resultado.get("extraccion")
    if extraccion is None or resultado.get("error") in ("COMUNICACION", "FORMATO", "CONTRATO"):
        return None
    if contrato_para(version) is ExtraccionPacienteV1:
        return normalizar_v1(extraccion)
    return extraccion


def evaluar_caso(caso: dict, resultado: dict, version: str) -> dict:
    esperado = caso["esperado"]
    extraccion = extraccion_evaluable(resultado, version)
    if extraccion is None:
        entidades_ok = {e: False for e in ENTIDADES}
        intenciones_ok, obtenidas = False, None
    else:
        obtenidas = extraccion["intenciones"]
        intenciones_ok = intenciones_correctas(esperado["intenciones"], obtenidas)
        entidades_ok = {e: entidad_correcta(e, esperado[e], extraccion.get(e)) for e in ENTIDADES}
    return {
        "id": caso["id"],
        "categoria": caso["categoria"],
        "error": resultado.get("error"),
        "detalle": resultado.get("detalle"),
        "respuesta_cruda": resultado.get("respuesta_cruda"),
        "origen": resultado.get("origen"),
        "intenciones_esperadas": esperado["intenciones"],
        "intenciones_obtenidas": obtenidas,
        "extraccion": extraccion,
        "intenciones_ok": intenciones_ok,
        "entidades_ok": entidades_ok,
        "completo_ok": intenciones_ok and all(entidades_ok.values()),
    }


# ── Simulación (sin API key): respuesta "perfecta" en el formato de cada versión ──

def simulacion_para(caso: dict, version: str) -> str:
    """Sin key, el script se puede probar igual: simula una respuesta que coincide con lo esperado."""
    datos = dict(caso["esperado"])
    if contrato_para(version) is ExtraccionPacienteV1:
        es_medica = "consulta_medica" in datos["intenciones"]
        intenciones = [i for i in datos["intenciones"] if i != "consulta_medica"] or ["otra"]
        datos = {**datos, "intenciones": intenciones, "es_consulta_medica": es_medica}
    return json.dumps(datos, ensure_ascii=False)


# ── Corrida retomable ──────────────────────────────────────────────────────────

def ruta_resultados(version: str) -> Path:
    return RAIZ_ENTREGA / "evidencia" / f"evaluacion_{version}.json"


def cargar_resultados(ruta: Path) -> dict:
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return {"resultados": {}}


def guardar_resultados(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def evaluar(set_casos: list[dict], version: str, ruta: Path, pausa: float = PAUSA_POR_DEFECTO,
            procesar: Callable = procesar_mensaje, hay_api: bool = True) -> dict:
    """
    Evalúa los casos que todavía no tienen resultado en `ruta`, guardando después de cada uno.
    Devuelve el contenido completo del archivo de resultados.
    """
    datos = cargar_resultados(ruta)
    datos.update({"version": version, "fecha": f"{date.today():%d/%m/%Y}"})
    pendientes = [c for c in set_casos if c["id"] not in datos["resultados"]]
    if len(pendientes) < len(set_casos):
        print(f"  Retomando: {len(set_casos) - len(pendientes)} ya evaluados, faltan {len(pendientes)}.")

    for n, caso in enumerate(pendientes, start=1):
        if hay_api and n > 1 and pausa > 0:
            time.sleep(pausa)
        resultado = procesar(caso["mensaje"], simulacion_para(caso, version), version)
        evaluado = evaluar_caso(caso, resultado, version)
        datos["resultados"][caso["id"]] = evaluado
        datos["origen"] = resultado.get("origen", datos.get("origen"))
        guardar_resultados(ruta, datos)
        marca = "✓" if evaluado["completo_ok"] else ("~" if evaluado["intenciones_ok"] else "✗")
        print(f"  [{len(datos['resultados']):>2}/{len(set_casos)}] {marca} {caso['id']} "
              f"{evaluado['intenciones_obtenidas'] or evaluado['error']}")
    return datos


# ── Métricas e informe ─────────────────────────────────────────────────────────

def calcular_metricas(evaluados: list[dict]) -> dict:
    total = len(evaluados)
    if total == 0:
        return {"total": 0}
    def pct(n: int, de: int = total) -> float:
        return round(100 * n / de, 1)
    json_ok = [e for e in evaluados if e["error"] not in ("COMUNICACION", "FORMATO")]
    contrato_ok = [e for e in json_ok if e["error"] != "CONTRATO"]
    entidades_bien = sum(sum(e["entidades_ok"].values()) for e in evaluados)
    return {
        "total": total,
        "json_valido": pct(len(json_ok)),
        "cumple_contrato": pct(len(contrato_ok)),
        "intenciones_exactas": pct(sum(e["intenciones_ok"] for e in evaluados)),
        "entidades_correctas": pct(entidades_bien, total * len(ENTIDADES)),
        "completamente_correctos": pct(sum(e["completo_ok"] for e in evaluados)),
        "errores": {tipo: sum(e["error"] == tipo for e in evaluados)
                    for tipo in ("COMUNICACION", "FORMATO", "CONTRATO", "REGLA")},
    }


def metricas_por_categoria(evaluados: list[dict]) -> dict:
    categorias: dict[str, list[dict]] = {}
    for e in evaluados:
        categorias.setdefault(e["categoria"], []).append(e)
    return {cat: calcular_metricas(items) for cat, items in categorias.items()}


def informe_markdown(datos: dict, set_casos: list[dict]) -> str:
    orden = [c["id"] for c in set_casos]
    evaluados = [datos["resultados"][i] for i in orden if i in datos["resultados"]]
    m = calcular_metricas(evaluados)
    lineas = [
        f"### Evaluación — prompt `{datos['version']}` · {datos.get('origen', '—')} · {datos.get('fecha', '')}",
        "",
        f"Mensajes evaluados: **{m['total']}** de {len(set_casos)}",
        "",
        "| Métrica | Resultado |",
        "|---|---|",
        f"| JSON válido | {m['json_valido']} % |",
        f"| Cumple el contrato | {m['cumple_contrato']} % |",
        f"| Intenciones exactas | {m['intenciones_exactas']} % |",
        f"| Entidades correctas | {m['entidades_correctas']} % |",
        f"| **Mensajes completamente correctos** (hipótesis B.5: ≥ 90 %) | **{m['completamente_correctos']} %** |",
        "",
        "Errores por etapa: " + ", ".join(f"{k} {v}" for k, v in m["errores"].items()),
        "",
        "| Categoría | Mensajes | Intenciones exactas | Completamente correctos |",
        "|---|---|---|---|",
    ]
    for cat, mc in metricas_por_categoria(evaluados).items():
        lineas.append(f"| {cat} | {mc['total']} | {mc['intenciones_exactas']} % | {mc['completamente_correctos']} % |")

    fallos = [e for e in evaluados if not e["completo_ok"]]
    lineas += ["", f"**Mensajes con algún error ({len(fallos)}):**", "",
               "| id | Categoría | Intenciones esperadas | Obtenidas | Entidades mal | Error |",
               "|---|---|---|---|---|---|"]
    for e in fallos:
        mal = [k for k, ok in e["entidades_ok"].items() if not ok] if e["extraccion"] else ["(sin extracción)"]
        obtenidas = ", ".join(e["intenciones_obtenidas"]) if e["intenciones_obtenidas"] else "—"
        lineas.append(f"| {e['id']} | {e['categoria']} | {', '.join(e['intenciones_esperadas'])} | {obtenidas} | "
                      f"{', '.join(mal) or '—'} | {e['error'] or '—'} |")
    return "\n".join(lineas)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="Evalúa la extracción sobre el set de 50 mensajes.")
    parser.add_argument("version", nargs="?", default=PROMPT_VERSION, help="versión de prompt (v1, v2, zeroshot…)")
    parser.add_argument("--pausa", type=float, default=PAUSA_POR_DEFECTO, help="segundos entre llamadas a la API")
    parser.add_argument("--limite", type=int, default=None, help="evaluar solo los primeros N mensajes")
    parser.add_argument("--desde-cero", action="store_true", help="descartar resultados guardados")
    args = parser.parse_args()

    if not (RAIZ_ENTREGA / "prompts" / f"extraccion_{args.version}.txt").exists():
        print(f"❌ No existe el prompt '{args.version}'.")
        sys.exit(1)
    try:
        hay_api = detectar_proveedor() is not None
    except ConfiguracionError as e:
        print(f"❌ Error de configuración: {e}")
        sys.exit(1)

    set_casos = json.loads(RUTA_SET.read_text(encoding="utf-8"))[: args.limite]
    ruta = ruta_resultados(args.version) if hay_api else ruta_resultados(f"{args.version}_simulacion")
    if args.desde_cero and ruta.exists():
        ruta.unlink()

    if hay_api:
        minutos = len(set_casos) * (args.pausa + 2) / 60
        print(f"Evaluando {len(set_casos)} mensajes con el prompt {args.version} (≈ {minutos:.0f} min).")
    else:
        print("⚠️  MODO SIMULACIÓN: sin API key, las respuestas simuladas coinciden con lo esperado "
              "(sirve para probar el script, no para medir el modelo).")

    datos = evaluar(set_casos, args.version, ruta, pausa=args.pausa, hay_api=hay_api)
    print("\n" + informe_markdown(datos, set_casos))
    print(f"\nResultados guardados en {ruta.relative_to(RAIZ_ENTREGA.parent)}")


if __name__ == "__main__":
    main()
