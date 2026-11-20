"""Utilidades para armar prompts de forma segura.

El texto del usuario (CV o vacante pegada) se envuelve en etiquetas XML para que el modelo lo trate
como DATOS y no como instrucciones (mitigación de prompt injection, riesgo R9 del SPEC).
"""

import re


def delimitar(etiqueta: str, texto: str) -> str:
    """Envuelve `texto` en <etiqueta>…</etiqueta>, neutralizando cierres falsos dentro del texto."""
    seguro = texto.replace(f"</{etiqueta}>", f"</ {etiqueta}>")
    return f"<{etiqueta}>\n{seguro}\n</{etiqueta}>"


def extraer_delimitado(etiqueta: str, mensaje: str) -> str:
    """Recupera el contenido de <etiqueta>…</etiqueta>; si no hay etiquetas, devuelve el mensaje completo."""
    coincidencia = re.search(rf"<{etiqueta}>\n?(.*?)\n?</{etiqueta}>", mensaje, flags=re.DOTALL)
    return coincidencia.group(1) if coincidencia else mensaje
