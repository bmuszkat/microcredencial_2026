"""
Configuración: API keys desde .env y selección del proveedor de LLM.

La API key NUNCA se escribe en el código: se lee del archivo .env de la raíz
del repo, que está en el .gitignore. En el repositorio solo se sube .env.example.

Selección del proveedor (spec `proveedor-llm`):
    - Si LLM_PROVIDER está definido, se usa ese proveedor. Si su key falta, es un
      error: no se cae en silencio a otro proveedor, porque el lote documentado
      tiene que corresponder al modelo que decimos haber usado.
    - Si no está definido, se usa el primero con key válida (orden de PROVEEDORES).
    - Si no hay ninguna key, detectar_proveedor() devuelve None → modo simulación.
"""

import os
import ssl
from pathlib import Path
from typing import Optional

# entrega_2/clinica/config.py → parents[1] = entrega_2/, parents[2] = raíz del repo
RAIZ_ENTREGA = Path(__file__).resolve().parents[1]
RAIZ_REPO = Path(__file__).resolve().parents[2]

# Orden de preferencia automática. Groq primero: es el proveedor elegido en la Entrega 1 (A.4).
PROVEEDORES = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

# Modelo por defecto de cada proveedor; se cambia con <PROVEEDOR>_MODEL en el .env.
MODELOS_POR_DEFECTO = {
    "groq": "openai/gpt-oss-20b",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-5-5",
    "gemini": "gemini-2.5-flash",
}


class ConfiguracionError(Exception):
    """El .env pide algo que no se puede cumplir (proveedor desconocido o sin key)."""


def cargar_env(env_path: Path = RAIZ_REPO / ".env") -> None:
    """Carga el .env de la raíz del repo. No pisa variables ya definidas en el entorno."""
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
    except ImportError:
        # Alternativa sin librerías: leer el archivo línea por línea.
        if env_path.exists():
            for linea in env_path.read_text(encoding="utf-8-sig").splitlines():
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    clave, valor = linea.split("=", 1)
                    os.environ.setdefault(clave.strip(), valor.strip().strip("'\""))


def crear_contexto_ssl() -> ssl.SSLContext:
    """Contexto SSL con verificación. Usa `certifi` si está instalado (útil en macOS)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def key_valida(variable: str) -> Optional[str]:
    """Devuelve la API key si está configurada y no es el placeholder del .env.example."""
    valor = os.getenv(variable, "").strip()
    if not valor or "tu_api_key" in valor:
        return None
    return valor


def modelo_de(proveedor: str) -> str:
    """Modelo a usar para el proveedor: <PROVEEDOR>_MODEL del .env o el valor por defecto."""
    return os.getenv(f"{proveedor.upper()}_MODEL", "").strip() or MODELOS_POR_DEFECTO[proveedor]


def detectar_proveedor() -> Optional[tuple[str, str]]:
    """
    Devuelve (proveedor, api_key), o None si no hay ninguna key (modo simulación).
    Lanza ConfiguracionError si LLM_PROVIDER pide un proveedor desconocido o sin key.
    """
    elegido = os.getenv("LLM_PROVIDER", "").strip().lower()

    if elegido:
        if elegido not in PROVEEDORES:
            opciones = ", ".join(PROVEEDORES)
            raise ConfiguracionError(f"LLM_PROVIDER='{elegido}' no es válido. Opciones: {opciones}")
        key = key_valida(PROVEEDORES[elegido])
        if key is None:
            raise ConfiguracionError(
                f"LLM_PROVIDER={elegido} pero falta {PROVEEDORES[elegido]} en el .env"
            )
        return elegido, key

    for nombre, variable in PROVEEDORES.items():
        key = key_valida(variable)
        if key:
            return nombre, key
    return None


cargar_env()
SSL_CONTEXT = crear_contexto_ssl()
