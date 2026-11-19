"""Helpers para leer variables de entorno con tipos y valores por defecto.

Están separados de settings.py para poder probarlos sin recargar la configuración de Django.
"""

import os

from django.core.exceptions import ImproperlyConfigured

# Solo se usa en desarrollo (DEBUG=True). En producción la clave debe venir del entorno.
SECRET_KEY_DESARROLLO = "django-insecure-solo-para-desarrollo-local"


def leer_texto(nombre: str, por_defecto: str = "") -> str:
    """Devuelve la variable como texto, sin espacios sobrantes."""
    return os.environ.get(nombre, por_defecto).strip()


def leer_bool(nombre: str, por_defecto: bool = False) -> bool:
    """Interpreta 'true', '1', 'si', 'sí', 'yes' u 'on' (sin importar mayúsculas) como True."""
    valor = os.environ.get(nombre)
    if valor is None or valor.strip() == "":
        return por_defecto
    return valor.strip().lower() in {"true", "1", "si", "sí", "yes", "on"}


def leer_int(nombre: str, por_defecto: int) -> int:
    """Lee un entero; si el valor no es válido, lanza un error que dice qué variable revisar."""
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        return por_defecto
    try:
        return int(valor)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{nombre} debe ser un número entero (valor actual: {valor!r}).") from exc


def leer_float(nombre: str, por_defecto: float) -> float:
    """Lee un número decimal; si el valor no es válido, lanza un error que dice qué variable revisar."""
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        return por_defecto
    try:
        return float(valor)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{nombre} debe ser un número decimal (valor actual: {valor!r}).") from exc


def obtener_secret_key(valor: str, debug: bool) -> str:
    """Usa la clave del entorno; sin ella, solo se permite una clave de desarrollo si DEBUG=True."""
    if valor:
        return valor
    if debug:
        return SECRET_KEY_DESARROLLO
    raise ImproperlyConfigured("Define DJANGO_SECRET_KEY en el archivo .env cuando DJANGO_DEBUG=False.")
