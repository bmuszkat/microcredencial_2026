
import os
import json
import ssl
import urllib.request
import urllib.error


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

ssl_context = ssl.create_default_context()

GEMINI_MODELS = [
    "gemini-3.8-flash"
]

OPENAI_MODEL = "gpt-4o-mini"

API_TIMEOUT = 120


# ============================================================
# CARGA AUTOMÁTICA DEL ARCHIVO .ENV
# ============================================================

def cargar_env_local():
    """
    Lee el archivo .env ubicado en la misma carpeta
    que este script.

    No requiere instalar librerías externas.
    """

    env_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".env"
    )

    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8-sig") as archivo:
        for linea in archivo:
            linea = linea.strip()

            if not linea or linea.startswith("#"):
                continue

            if "=" not in linea:
                continue

            clave, valor = linea.split("=", 1)

            clave = clave.strip()
            valor = valor.strip().strip("'\"")

            os.environ[clave] = valor


cargar_env_local()


# ============================================================
# PASO 1 - MENSAJE DE PRUEBA NO ESTRUCTURADO
# ============================================================

MENSAJE_PACIENTE = """
Hola, buen día. Soy Juan Pérez, DNI 30123456.

Tengo un turno con el oftalmólogo para el jueves a las 15 hs,
pero necesito cambiarlo para el viernes por la mañana.

Además, el lunes pasado me hice un estudio de campo visual
y quería saber si los resultados ya están disponibles.

¿Me pueden confirmar ambas cosas?
"""


# ============================================================
# PASO 2 - CONEXIÓN A GOOGLE GEMINI
# ============================================================

def llamar_gemini_api(prompt: str, api_key: str) -> str:
    """
    Consulta Google Gemini mediante su API REST.

    Prueba los modelos configurados en GEMINI_MODELS.
    """

    errores = []

    for modelo in GEMINI_MODELS:

        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{modelo}:generateContent"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        datos = json.dumps(payload).encode("utf-8")

        solicitud = urllib.request.Request(
            url,
            data=datos,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(
                solicitud,
                context=ssl_context,
                timeout=API_TIMEOUT
            ) as respuesta:

                resultado = json.loads(
                    respuesta.read().decode("utf-8")
                )

                partes = (
                    resultado["candidates"][0]
                    ["content"]["parts"]
                )

                texto = "".join(
                    parte.get("text", "")
                    for parte in partes
                ).strip()

                if not texto:
                    raise RuntimeError(
                        "Gemini devolvió una respuesta vacía."
                    )

                return texto

        except urllib.error.HTTPError as error:

            detalle = error.read().decode(
                "utf-8",
                errors="replace"
            )

            errores.append(
                f"{modelo}: HTTP {error.code} - "
                f"{detalle[:400]}"
            )

        except Exception as error:

            errores.append(
                f"{modelo}: "
                f"{type(error).__name__}: {error}"
            )

    raise RuntimeError(
        "No se pudo obtener una respuesta de Gemini. "
        + " | ".join(errores)
    )


# ============================================================
# PASO 2 - CONEXIÓN A OPENAI
# ============================================================

def llamar_openai_api(prompt: str, api_key: str) -> str:
    """
    Consulta OpenAI mediante su API REST.

    Utiliza el modelo configurado en OPENAI_MODEL.
    """

    url = "https://api.openai.com/v1/chat/completions"

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7
    }

    datos = json.dumps(payload).encode("utf-8")

    solicitud = urllib.request.Request(
        url,
        data=datos,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            solicitud,
            context=ssl_context,
            timeout=API_TIMEOUT
        ) as respuesta:

            resultado = json.loads(
                respuesta.read().decode("utf-8")
            )

            texto = resultado["choices"][0]["message"]["content"]

            if not texto:
                raise RuntimeError(
                    "OpenAI devolvió una respuesta vacía."
                )

            return texto.strip()

    except urllib.error.HTTPError as error:

        detalle = error.read().decode(
            "utf-8",
            errors="replace"
        )

        raise RuntimeError(
            f"OpenAI HTTP {error.code}: {detalle[:500]}"
        ) from error


# ============================================================
# SELECCIÓN DEL PROVEEDOR
# ============================================================

def obtener_proveedores_disponibles():
    """
    Determina qué proveedor utilizar.

    AI_PROVIDER puede ser:
        auto
        gemini
        openai

    En modo auto:
        1. Intenta Gemini.
        2. Si falla, intenta OpenAI.
        3. Si no hay claves, usa simulación.
    """

    proveedor = os.getenv(
        "AI_PROVIDER",
        "auto"
    ).strip().lower()

    if proveedor not in ("auto", "gemini", "openai"):
        raise ValueError(
            "AI_PROVIDER debe ser auto, gemini u openai."
        )

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    gemini_valida = (
        bool(gemini_key)
        and gemini_key != "tu_api_key_de_gemini_aqui"
    )

    openai_valida = (
        bool(openai_key)
        and openai_key != "sk-tu_api_key_de_openai_aqui"
    )

    proveedores = []

    if proveedor in ("auto", "gemini") and gemini_valida:
        proveedores.append(
            ("Google Gemini", llamar_gemini_api, gemini_key)
        )

    if proveedor in ("auto", "openai") and openai_valida:
        proveedores.append(
            ("OpenAI", llamar_openai_api, openai_key)
        )

    return proveedores


# ============================================================
# PASO 2 Y 3 - PROMPT INGENUO Y AUDITORÍA
# ============================================================

def ejecutar_prompt_ingenuo_con_llm(mensaje: str) -> dict:
    """
    Envía el mensaje del paciente a un LLM real si hay
    una API Key configurada.

    Si no hay claves, ejecuta una simulación.

    El objetivo de la actividad es observar los riesgos
    de utilizar un LLM sin información verificada.
    """

    prompt_ingenuo = f"""
    Sos el asistente de atención al paciente de una
    clínica especializada en oftalmología.

    Un paciente te envía el siguiente mensaje:

    "{mensaje}"

    Respondé al paciente indicando si su turno puede
    modificarse para el viernes por la mañana.

    También informale si los resultados de su estudio
    de campo visual ya están disponibles.
    """

    origen_respuesta = "SIMULACIÓN (Sin API Key válida)"

    respuesta_texto = ""

    errores = []

    try:
        proveedores = obtener_proveedores_disponibles()

        for nombre, funcion, api_key in proveedores:

            print(f"\nConsultando API de {nombre}...")

            try:
                respuesta_texto = funcion(
                    prompt_ingenuo,
                    api_key
                )

                origen_respuesta = f"API REAL - {nombre}"

                print(f"Respuesta recibida de {nombre}.")

                break

            except Exception as error:

                detalle = (
                    f"{nombre}: "
                    f"{type(error).__name__}: {error}"
                )

                errores.append(detalle)

                print(f"Error consultando {nombre}.")

        if not proveedores:

            respuesta_texto = (
                "Hola Juan, tu turno fue reprogramado "
                "exitosamente para el viernes a las 10:00 hs. "
                "Además, los resultados de tu estudio de campo "
                "visual ya están disponibles para retirar."
            )

        elif not respuesta_texto:

            origen_respuesta = "ERROR AL LLAMAR A LAS APIs"

            respuesta_texto = (
                "No se pudo obtener una respuesta "
                "de los proveedores de IA configurados."
            )

    except Exception as error:

        origen_respuesta = (
            f"ERROR DE CONFIGURACIÓN: "
            f"{type(error).__name__}: {error}"
        )

        respuesta_texto = (
            "No se pudo ejecutar la consulta al LLM."
        )

    return {
        "mensaje_recibido": mensaje.strip(),

        "proveedor_ejecutado": origen_respuesta,

        "respuesta_generada_por_llm": respuesta_texto.strip(),

        "errores_conexion": errores,

        "diagnostico_alucinacion": {

            "disponibilidad_verificada": False,

            "resultados_verificados": False,

            "motivo": (
                "El LLM no tiene acceso al sistema de turnos "
                "ni a la base de resultados médicos. "
                "No puede confirmar cambios ni disponibilidad "
                "de estudios sin consultar fuentes reales."
            ),

            "riesgo": (
                "ALTO - Posibilidad de confirmar turnos inexistentes "
                "o informar resultados no disponibles."
            )
        }
    }


# ============================================================
# PASO 4 Y 5 - FICHA PEAS
# ============================================================

def generar_ficha_peas_clinica() -> dict:
    """
    Genera la Ficha PEAS del asistente inteligente
    de una clínica especializada en oftalmología.

    P - Performance: Métricas y criterios de éxito.
    E - Environment: Usuarios y entorno.
    A - Actuators: Herramientas y acciones.
    S - Sensors: Datos de entrada.
    """

    return {
        "sistema": "Asistente Inteligente de Clínica Oftalmológica",

        "mapa_conceptual_6_piezas": {

            "1_Usuario (Entorno / Environment)": (
                "Pacientes y personal administrativo de la clínica "
                "(WhatsApp, Email, Sistema de Turnos)"
            ),

            "2_Datos (Sensores / Sensors)": (
                "Mensajes de pacientes, DNI, turnos existentes, "
                "disponibilidad de profesionales y estado de estudios"
            ),

            "3_Modelo": (
                "LLM (Simulado o Gemini/OpenAI)"
            ),

            "4_Herramientas (Actuadores / Actuators)": (
                "Consultar disponibilidad, crear turnos, "
                "modificar turnos, cancelar turnos y "
                "consultar estado de resultados médicos"
            ),

            "5_Reglas": (
                "Validación de identidad, disponibilidad de turnos, "
                "confirmación de cambios, privacidad de datos médicos "
                "y prohibición de interpretar resultados clínicos"
            ),

            "6_Salida (Performance)": (
                "Gestión correcta de turnos y consultas de resultados "
                "sin información inventada"
            )
        },

        "PEAS_clasico": {

            "Performance (Métricas)": (
                "Tiempo de respuesta inicial < 5 segundos, "
                "0 turnos duplicados, "
                "100% de operaciones verificadas contra el sistema, "
                "0 divulgaciones no autorizadas de datos médicos"
            ),

            "Environment (Entorno)": (
                "WhatsApp, Email, Sistema de Gestión de Turnos, "
                "Sistema de Resultados Médicos"
            ),

            "Actuators (Actuadores)": (
                "Crear, modificar y cancelar turnos, "
                "consultar disponibilidad, "
                "informar estado de resultados y enviar confirmaciones"
            ),

            "Sensors (Sensores)": (
                "Mensajes de pacientes, DNI, agendas médicas, "
                "turnos registrados y estado de estudios oftalmológicos"
            )
        },

        "señales_oportunidad": [
            (
                "1. Alto volumen de consultas repetitivas sobre turnos "
                "y resultados de estudios oftalmológicos"
            ),
            (
                "2. Procesos administrativos manuales que generan "
                "demoras y posibles errores"
            ),
            (
                "3. Sobrecarga del personal administrativo "
                "por consultas que podrían automatizarse"
            )
        ]
    }


# ============================================================
# EJECUCIÓN PRINCIPAL
# ============================================================

if __name__ == "__main__":

    print("\n" + "=" * 70)
    print("MICROCREDENCIAL CLASE 1 - CLÍNICA OFTALMOLÓGICA")
    print("=" * 70)

    # PASO 2 Y 3 - Auditoría
    resultado = ejecutar_prompt_ingenuo_con_llm(
        MENSAJE_PACIENTE
    )

    print("\n[PASO 2 Y 3] Auditoría del Prompt:")

    print(json.dumps(
        resultado,
        indent=2,
        ensure_ascii=False
    ))

    # Aviso si se ejecutó una simulación
    if "SIMULACIÓN" in resultado["proveedor_ejecutado"]:

        print("\nAVISO: Ejecutando en modo simulación.")

        print(
            "Para conectar una IA real, configurá "
            "GEMINI_API_KEY u OPENAI_API_KEY en .env"
        )

    # PASO 4 Y 5 - Ficha PEAS
    peas = generar_ficha_peas_clinica()

    print("\n[PASO 4 Y 5] Ficha PEAS:")

    print(json.dumps(
        peas,
        indent=2,
        ensure_ascii=False
    ))
