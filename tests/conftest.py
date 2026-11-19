"""Configuración global de pytest.

Garantiza dos cosas en TODAS las pruebas, sin que cada test tenga que pedirlo:
1. No hay API key de Anthropic: nada puede autenticarse contra la API real.
2. No se permiten conexiones de red fuera de la máquina: si algún código intenta salir
   a internet, la prueba falla con un error explícito en lugar de llamar a la API.
"""

import socket

import pytest

DIRECCIONES_LOCALES = {"127.0.0.1", "::1", "localhost"}


class RedNoPermitidaEnPruebas(RuntimeError):
    """Se lanza cuando una prueba intenta conectarse a un host externo."""


def _host_de(direccion) -> str:
    """Extrae el host de la dirección que recibe socket.connect (tupla o ruta de socket Unix)."""
    if isinstance(direccion, tuple) and direccion:
        return str(direccion[0])
    return "localhost"  # sockets Unix u otras familias locales


@pytest.fixture(autouse=True)
def sin_api_key(monkeypatch, settings):
    """Quita la API key del entorno y de la configuración de Django."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings.ANTHROPIC_API_KEY = ""


@pytest.fixture(autouse=True)
def bloquear_red(monkeypatch):
    """Bloquea conexiones y resolución DNS hacia hosts que no sean locales."""
    connect_original = socket.socket.connect
    getaddrinfo_original = socket.getaddrinfo

    def connect_vigilado(self, direccion):
        host = _host_de(direccion)
        if host not in DIRECCIONES_LOCALES:
            raise RedNoPermitidaEnPruebas(f"Las pruebas no pueden conectarse a {host!r}. Usa un proveedor LLM falso.")
        return connect_original(self, direccion)

    def getaddrinfo_vigilado(host, *args, **kwargs):
        if host is not None and str(host) not in DIRECCIONES_LOCALES:
            raise RedNoPermitidaEnPruebas(f"Las pruebas no pueden resolver {host!r}. Usa un proveedor LLM falso.")
        return getaddrinfo_original(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect_vigilado)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo_vigilado)
