
import os
import json
import ssl
import urllib.request
import urllib.error


# ============================================================
# CONFIGURACIÓN SSL
# ============================================================

ssl_context = ssl.create_default_context()


# ============================================================
# CARGA AUTOMÁTICA DEL ARCHIVO .ENV
# ============================================================

def cargar_env_local():
    """
    Lee el archivo .env ubicado en la misma carpeta
    que este script, sin requerir librerías externas.
    """
    env_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".env"
    )

    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()

                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip("'\"")


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
# PASO 2 - CONEXIÓN A APIs REALES (GEMINI / OPENAI)
# ============================================================

def llamar_gemini_api(prompt: str, api_key: str) -> str:
    """
    Invoca la API de Google Gemini utilizando urllib.
    No requiere instalar librerías externas.
    """

    modelos = [
        "gemini-3.8-flash"
    ]

    errores = []

    for modelo in modelos:
        url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{modelo}:generateContent"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ]
        }

        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(
                req,
                context=ssl_context,
                timeout=30
            ) as resp:

                res_data = json.loads(
                    resp.read().decode("utf-8")
                )

                return (
                    res_data["candidates"][0]
                    ["content"]["parts"][0]["text"]
                )

        except urllib.error.HTTPError as e:
            detalle = e.read().decode(
                "utf-8",
                errors="replace"
            )
            errores.append(
                f"{modelo}: HTTP {e.code} - {detalle[:300]}"
            )

        except Exception as e:
            errores.append(
                f"{modelo}: {type(e).__name__}: {e}"
            )

    raise RuntimeError(
        "No se pudo conectar con Google Gemini. "
        + " | ".join(errores)
    )


def llamar_openai_api(prompt: str, api_key: str) -> str:
    """
    Invoca la API de OpenAI utilizando urllib.
    """

    url = "https://api.openai.com/v1/chat/completions"

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )

    with urllib.request.urlopen(
        req,
        context=ssl_context,
        timeout=30
    ) as resp:

        res_data = json.loads(
            resp.read().decode("utf-8")
        )

        return res_data["choices"][0]["message"]["content"]


# ============================================================
# PASO 2 Y 3 - CONSULTA AL LLM Y AUDITORÍA
# ============================================================

def ejecutar_prompt_ingenuo_con_llm(mensaje: str) -> dict:
    """
    Envía el mensaje del paciente a un LLM real si existe
    una API Key configurada.

    Si no hay API Key, utiliza una respuesta simulada.

    El objetivo es demostrar el riesgo de alucinaciones
    cuando el modelo no tiene acceso a los sistemas reales.
    """

    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

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

    origen_respuesta = "SIMULACIÓN (Sin API Key)"
    respuesta_texto = ""

    try:
        if gemini_key and gemini_key != "tu_api_key_de_gemini_aqui":

            origen_respuesta = "API REAL - Google Gemini"

            respuesta_texto = llamar_gemini_api(
                prompt_ingenuo,
                gemini_key
            )

        elif openai_key and openai_key != "sk-tu_api_key_de_openai_aqui":

            origen_respuesta = "API REAL - OpenAI"

            respuesta_texto = llamar_openai_api(
                prompt_ingenuo,
                openai_key
            )

        else:
            origen_respuesta = "SIMULACIÓN (Sin API Key válida)"

            # Respuesta deliberadamente inventada para
            # demostrar el riesgo de alucinaciones.
            respuesta_texto = (
                "Hola Juan, tu turno fue reprogramado "
                "exitosamente para el viernes a las 10:00 hs. "
                "Además, los resultados de tu estudio de campo "
                "visual ya están disponibles para retirar."
            )

    except Exception as e:
        origen_respuesta = (
            f"ERROR AL LLAMAR A LA API "
            f"({type(e).__name__}): {e}"
        )

        respuesta_texto = (
            "Error de conexión con el proveedor de IA."
        )

    return {
        "mensaje_recibido": mensaje.strip(),

        "proveedor_ejecutado": origen_respuesta,

        "respuesta_generada_por_llm": respuesta_texto.strip(),

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

    PEAS:
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

    # Aviso cuando se ejecuta en modo simulación
    if "SIMULACIÓN" in resultado["proveedor_ejecutado"]:
        print("\nAVISO: Ejecutando en modo simulación.")
        print(
            "Para utilizar Gemini, configurá GEMINI_API_KEY "
            "en el archivo .env"
        )

    # PASO 4 Y 5 - Ficha PEAS
    peas = generar_ficha_peas_clinica()

    print("\n[PASO 4 Y 5] Ficha PEAS:")
    print(json.dumps(
        peas,
        indent=2,
        ensure_ascii=False
    ))
