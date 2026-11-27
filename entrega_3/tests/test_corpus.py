"""Estructura del corpus del RAG y coherencia con los datos del backend (spec `corpus-clinica`, design D3)."""

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

ENTREGA_3 = Path(__file__).resolve().parents[1]
CATEGORIAS = {"cargos", "cobertura", "preparacion_estudio", "resultados", "sedes_horarios", "documentacion"}


def cargar(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def corpus():
    return cargar(ENTREGA_3 / "corpus" / "corpus_clinica.json")


@pytest.fixture(scope="module")
def por_id(corpus):
    return {d["id"]: d for d in corpus}


@pytest.fixture(scope="module")
def agenda():
    return cargar(ENTREGA_3 / "datos" / "agenda.json")


def vigentes(corpus, categoria):
    return [d for d in corpus if d["metadatos"]["categoria"] == categoria and d["metadatos"]["vigente"]]


# ── Estructura ────────────────────────────────────────────────────────────────

def test_entre_10_y_15_documentos_con_ids_unicos(corpus):
    assert 10 <= len(corpus) <= 15
    ids = [d["id"] for d in corpus]
    assert len(ids) == len(set(ids))


def test_cada_documento_tiene_titulo_y_texto_rico(corpus):
    for d in corpus:
        assert set(d) == {"id", "titulo", "descripcion_semantica", "metadatos"}, d["id"]
        assert d["titulo"].strip(), d["id"]
        # "rico": explica el tema y trae formas de preguntarlo, no una línea suelta
        assert len(d["descripcion_semantica"]) >= 250, d["id"]


def test_metadatos_filtrables_validos(corpus):
    for d in corpus:
        m = d["metadatos"]
        assert m["categoria"] in CATEGORIAS, d["id"]
        assert isinstance(m["vigente"], bool), d["id"]
        assert isinstance(m["version"], int), d["id"]
        # Chroma solo acepta metadatos escalares
        assert all(isinstance(v, (str, int, float, bool)) for v in m.values()), d["id"]


def test_hay_cargos_cobertura_y_preparacion_vigentes(corpus):
    for categoria in ("cargos", "cobertura", "preparacion_estudio"):
        assert vigentes(corpus, categoria), categoria


def test_montos_con_formato_unico(corpus):
    # El guardrail compara montos: en el corpus se escriben siempre como $12.000
    for d in corpus:
        for monto in re.findall(r"\$\s?\d[\d.]*\d", d["descripcion_semantica"]):   # sin el punto final de la oración
            assert re.fullmatch(r"\$\d{1,3}(\.\d{3})+", monto), (d["id"], monto)


# ── Versión derogada ──────────────────────────────────────────────────────────

def test_politica_de_cargos_vigente_y_derogada(corpus):
    cargos = [d for d in corpus if d["metadatos"]["categoria"] == "cargos"]
    vigente = [d for d in cargos if d["metadatos"]["vigente"]]
    derogada = [d for d in cargos if not d["metadatos"]["vigente"]]
    assert len(vigente) == 1 and len(derogada) == 1
    mv, md = vigente[0]["metadatos"], derogada[0]["metadatos"]
    assert md["version"] < mv["version"]
    assert (md["monto"], md["umbral_horas"]) != (mv["monto"], mv["umbral_horas"])
    assert "derogada" in derogada[0]["descripcion_semantica"]


# ── Coherencia con el backend ─────────────────────────────────────────────────

def test_cargo_vigente_igual_a_la_politica_del_backend(corpus):
    politica = cargar(ENTREGA_3 / "datos" / "politica_cargos.json")
    [vigente] = vigentes(corpus, "cargos")
    assert vigente["metadatos"]["monto"] == politica["monto"]
    assert vigente["metadatos"]["umbral_horas"] == politica["umbral_horas"]
    texto = vigente["descripcion_semantica"]
    assert f"${politica['monto']:,}".replace(",", ".") in texto
    assert f"{politica['umbral_horas']} horas" in texto


def test_una_cobertura_por_cada_obra_social_del_padron(corpus):
    padron = cargar(ENTREGA_3 / "datos" / "padron.json")["pacientes"]
    obras = {p["obra_social"] for p in padron}
    coberturas = [d["metadatos"]["obra_social"] for d in vigentes(corpus, "cobertura")]
    assert sorted(coberturas) == sorted(obras)


def test_cada_profesional_figura_en_su_sede_con_su_especialidad(corpus, agenda):
    sedes = {d["metadatos"]["sede"]: d["descripcion_semantica"] for d in vigentes(corpus, "sedes_horarios")}
    assert set(sedes) == {p["sede"] for p in agenda["profesionales"]}
    for p in agenda["profesionales"]:
        texto = sedes[p["sede"]]
        assert p["nombre"] in texto, p
        assert p["especialidad"].lower() in texto.lower(), p
        otras = [s for s in sedes if s != p["sede"]]
        assert all(p["nombre"] not in sedes[s] for s in otras), p


def test_el_corpus_no_nombra_profesionales_que_no_existen(corpus, agenda):
    nombres = {p["nombre"] for p in agenda["profesionales"]}
    for d in corpus:
        for nombre in re.findall(r"Dra?\. [A-ZÁÉÍÓÚ]\w+", d["descripcion_semantica"]):
            assert nombre in nombres, (d["id"], nombre)


def test_los_turnos_de_la_agenda_caen_en_el_horario_de_su_sede(corpus, agenda):
    horario = {}
    for d in vigentes(corpus, "sedes_horarios"):
        m = re.search(r"de lunes a viernes de (\d+) a (\d+) horas", d["descripcion_semantica"])
        horario[d["metadatos"]["sede"]] = (int(m.group(1)), int(m.group(2)))
    sede_de = {p["nombre"]: p["sede"] for p in agenda["profesionales"]}
    for t in agenda["turnos_libres"] + agenda["turnos_reservados"]:
        momento = datetime.fromisoformat(f"{t['fecha']}T{t['hora']}")
        apertura, cierre = horario[sede_de[t["profesional"]]]
        assert momento.weekday() < 5, t
        assert apertura <= momento.hour < cierre, t


def dias_habiles(desde: date, hasta: date) -> int:
    dias, actual = 0, desde
    while actual < hasta:
        actual += timedelta(days=1)
        dias += actual.weekday() < 5
    return dias


def test_las_entregas_estimadas_respetan_el_plazo_publicado(por_id):
    plazo = por_id["RES-PLAZOS-RETIRO"]["metadatos"]["plazo_dias_habiles"]
    assert f"{plazo} días hábiles" in por_id["RES-PLAZOS-RETIRO"]["descripcion_semantica"]
    estudios = cargar(ENTREGA_3 / "datos" / "estudios.json")["estudios"]
    con_entrega = [e for e in estudios if e["entrega_estimada"]]
    assert con_entrega
    for e in con_entrega:
        realizado = date.fromisoformat(e["fecha_realizacion"])
        assert dias_habiles(realizado, date.fromisoformat(e["entrega_estimada"])) <= plazo, e


def test_cada_estudio_del_backend_tiene_su_preparacion(corpus):
    estudios = {e["estudio"].lower() for e in cargar(ENTREGA_3 / "datos" / "estudios.json")["estudios"]}
    textos = " ".join(d["descripcion_semantica"].lower() for d in vigentes(corpus, "preparacion_estudio"))
    for estudio in estudios:
        assert estudio in textos, estudio
