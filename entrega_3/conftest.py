"""Permite que pytest importe los módulos de entrega_3 y el paquete `clinica` de entrega_2 corriendo desde la raíz del repo."""

import sys
from pathlib import Path

ENTREGA_3 = Path(__file__).resolve().parent
sys.path.insert(0, str(ENTREGA_3.parent / "entrega_2"))  # se reusa clinica/ sin moverlo (design D1)
sys.path.insert(0, str(ENTREGA_3))
