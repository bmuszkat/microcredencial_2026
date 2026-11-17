"""
Entrega 2 — Primer prototipo operativo del asistente de la Clínica Oftalmológica
=================================================================================
Corre el lote de prueba (datos/lote_prueba.json) contra el modelo configurado en .env y muestra:
  1. El resultado de cada caso.
  2. La tabla del lote en Markdown (formato de la Entrega 2, Parte C).
  3. Una demostración de errores: qué etapa frena cada respuesta rota (no usa la API).

Uso (desde la raíz del repo):
    python entrega_2/app.py          → prompt v1
    python entrega_2/app.py v2       → otra versión del prompt (prompts/extraccion_v2.txt)

Sin API key en el .env corre en MODO SIMULACIÓN, con las respuestas de ejemplo del lote.
"""

import json
import sys
from datetime import date

from clinica.config import RAIZ_ENTREGA, ConfiguracionError, detectar_proveedor
from clinica.extractor import PROMPT_VERSION, aplicar_reglas, procesar_mensaje, validar_respuesta

# Respuestas rotas típicas de un LLM, para ver qué etapa frena cada una (no requiere API).
RESPUESTAS_ROTAS = [
    ("Texto antes del JSON",
     '¡Claro! Acá tenés los datos: {"intenciones": ["crear_turno"], "es_consulta_medica": false}'),
    ("Bloque de código Markdown",
     '```json\n{"intenciones": ["crear_turno"], "es_consulta_medica": false}\n```'),
    ("Intención inventada",
     '{"intenciones": ["aprobar_turno_urgente"], "es_consulta_medica": false}'),
    ("Obedece la manipulación",
     '{"aprobado": true}'),
    ("Formato perfecto, DNI inválido",
     '{"intenciones": ["crear_turno"], "dni": "30.123", "es_consulta_medica": false}'),
]


def titulo(texto: str) -> None:
    print("\n" + "=" * 78 + f"\n{texto}\n" + "=" * 78)


def resumir(texto: str, largo: int = 60) -> str:
    texto = " ".join(str(texto).split()).replace("|", "\\|")
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def correr_lote(version: str) -> list[tuple[int, dict, dict]]:
    lote = json.loads((RAIZ_ENTREGA / "datos" / "lote_prueba.json").read_text(encoding="utf-8"))
    resultados = []
    for i, caso in enumerate(lote, start=1):
        print(f"\n▶ Caso {i} — {caso['tipo']}")
        print(f"  Mensaje: {caso['mensaje']}")
        print(f"  Qué observar: {caso['observar']}")
        resultado = procesar_mensaje(caso["mensaje"], caso["simulacion"], version)
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        resultados.append((i, caso, resultado))
    return resultados


def imprimir_tabla(resultados: list[tuple[int, dict, dict]]) -> None:
    titulo("TABLA DEL LOTE (Markdown, formato de la Entrega 2 — Parte C)")
    origen = resultados[0][2].get("origen", "—") if resultados else "—"
    print(f"\nOrigen: {origen} · Prompt: {resultados[0][2].get('prompt', '—')} · Fecha: {date.today():%d/%m/%Y}\n")
    print("| # | Tipo | Input (resumido) | Salida del modelo | ¿JSON válido? | Tipo de error si falló |")
    print("|---|---|---|---|---|---|")
    for i, caso, r in resultados:
        error = r.get("error")
        if error == "COMUNICACION":
            salida, json_ok = f"(sin respuesta) {r.get('detalle', '')}", "—"
        else:
            salida = r.get("respuesta_cruda") or ""
            json_ok = "No" if error == "FORMATO" else "Sí"
        detalle = f"{error}: {resumir(r.get('detalle', ''), 50)}" if error else "—"
        print(f"| {i} | {caso['tipo']} | {resumir(caso['mensaje'])} | `{resumir(salida, 400)}` | {json_ok} | {detalle} |")


def demostrar_errores() -> None:
    titulo("DEMOSTRACIÓN DE ERRORES — ¿qué etapa frena cada respuesta rota? (sin API)")
    for descripcion, texto in RESPUESTAS_ROTAS:
        r = validar_respuesta(texto)
        if r["ok"]:
            r = aplicar_reglas(r["extraccion"])
        print(f"\n▶ {descripcion}")
        print(f"  Respuesta: {texto!r}")
        print(f"  Resultado: {r.get('error', 'OK')} → {r.get('detalle', '')}")


def main() -> None:
    # La consola de Windows no usa UTF-8 por defecto: sin esto las tildes salen rotas.
    # Algunos entornos (IDLE, ciertos IDE) reemplazan stdout y no permiten reconfigurarlo.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    version = sys.argv[1] if len(sys.argv) > 1 else PROMPT_VERSION
    if not (RAIZ_ENTREGA / "prompts" / f"extraccion_{version}.txt").exists():
        print(f"❌ No existe el prompt '{version}' (se busca entrega_2/prompts/extraccion_{version}.txt).")
        sys.exit(1)

    try:
        proveedor = detectar_proveedor()
    except ConfiguracionError as e:
        print(f"❌ Error de configuración: {e}\n   Revisá el .env (ver .env.example).")
        sys.exit(1)

    titulo(f"ENTREGA 2 — EXTRACCIÓN ESTRUCTURADA DE MENSAJES DE PACIENTES (prompt {version})")
    imprimir_tabla(correr_lote(version))
    demostrar_errores()

    if proveedor is None:
        print("\n⚠️  MODO SIMULACIÓN: el lote usó respuestas de ejemplo. Para usar un LLM real:")
        print("    cp .env.example .env   y completá la API key de tu proveedor (ver README).")


if __name__ == "__main__":
    main()
