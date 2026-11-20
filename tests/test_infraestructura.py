"""Pruebas de la infraestructura de pruebas (T03): bloqueo de red y ProveedorFalso."""

import os
import socket
import urllib.request

import pytest

from tests.conftest import RedNoPermitidaEnPruebas
from tests.falsos import ProveedorFalso, RespuestasAgotadas


class TestBloqueoDeRed:
    def test_conexion_externa_por_ip_se_bloquea(self):
        with pytest.raises(RedNoPermitidaEnPruebas, match="1.1.1.1"):
            socket.create_connection(("1.1.1.1", 443), timeout=1)

    def test_resolucion_dns_externa_se_bloquea(self):
        with pytest.raises(RedNoPermitidaEnPruebas, match="api.anthropic.com"):
            socket.getaddrinfo("api.anthropic.com", 443)

    def test_peticion_http_externa_se_bloquea(self):
        with pytest.raises(RedNoPermitidaEnPruebas):
            urllib.request.urlopen("https://api.anthropic.com", timeout=1)

    def test_conexion_local_sigue_permitida(self):
        """El bloqueo no debe romper conexiones locales (por ejemplo, servidores de prueba)."""
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.bind(("127.0.0.1", 0))
        servidor.listen(1)
        puerto = servidor.getsockname()[1]
        try:
            cliente = socket.create_connection(("127.0.0.1", puerto), timeout=1)
            cliente.close()
        finally:
            servidor.close()


class TestSinApiKey:
    def test_no_hay_api_key_en_el_entorno(self):
        assert "ANTHROPIC_API_KEY" not in os.environ

    def test_no_hay_api_key_en_settings(self, settings):
        assert settings.ANTHROPIC_API_KEY == ""


class TestProveedorFalso:
    def test_devuelve_respuestas_en_orden(self):
        falso = ProveedorFalso(chats=["primera", "segunda"])
        assert falso.chat_con_herramientas("sis", [], []) == "primera"
        assert falso.chat_con_herramientas("sis", [], []) == "segunda"

    def test_lanza_excepciones_programadas(self):
        falso = ProveedorFalso(estructuradas=[TimeoutError("la API tardó demasiado")])
        with pytest.raises(TimeoutError, match="tardó"):
            falso.generar_estructurado("sis", "cv", dict)

    def test_falla_si_se_llama_de_mas(self):
        falso = ProveedorFalso(estructuradas=["unica"])
        falso.generar_estructurado("sis", "cv", dict)
        with pytest.raises(RespuestasAgotadas):
            falso.generar_estructurado("sis", "cv", dict)

    def test_registra_cada_llamada(self):
        falso = ProveedorFalso(estructuradas=["ok"])
        falso.generar_estructurado("sistema X", "texto del cv", dict)
        assert falso.llamadas == [
            {"metodo": "generar_estructurado", "sistema": "sistema X", "mensaje": "texto del cv", "esquema": dict}
        ]

    def test_registra_una_copia_de_los_mensajes(self):
        falso = ProveedorFalso(chats=["ok"])
        mensajes = [{"rol": "user", "contenido": "hola"}]
        falso.chat_con_herramientas("sis", mensajes, [])
        mensajes.append({"rol": "assistant", "contenido": "agregado después"})
        assert len(falso.llamadas[0]["mensajes"]) == 1
