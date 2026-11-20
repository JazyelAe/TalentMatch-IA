"""Pruebas del aviso de modo demo, páginas de error y logging seguro (T23)."""

import logging

import pytest
from django.core.management import call_command
from django.test import Client

from services.llm import ConexionLLMError
from tests.archivos_cv import TEXTO_CV

pytestmark = pytest.mark.django_db
AVISO_DEMO = "<strong>Modo demo:</strong>"
FRAGMENTO_CV = "startup de logistica"  # aparece en el CV de prueba


class TestAvisoModoDemo:
    @pytest.mark.parametrize("url", ["/", "/analizar/", "/historial/"])
    def test_visible_sin_api_key(self, client, url):
        assert AVISO_DEMO in client.get(url).content.decode()

    def test_oculto_con_api_key(self, client, settings):
        settings.ANTHROPIC_API_KEY = "sk-ant-prueba"
        settings.LLM_PROVEEDOR = "anthropic"
        assert AVISO_DEMO not in client.get("/").content.decode()

    def test_visible_si_se_fuerza_el_demo(self, client, settings):
        settings.ANTHROPIC_API_KEY = "sk-ant-prueba"
        settings.LLM_PROVEEDOR = "demo"
        assert AVISO_DEMO in client.get("/").content.decode()


def test_aviso_de_privacidad_en_el_historial(client):
    assert "El historial es compartido" in client.get("/historial/").content.decode()


class TestPaginasDeError:
    def test_404_propia(self, client):
        respuesta = client.get("/no-existe/")
        assert respuesta.status_code == 404
        assert "No encontramos esta página" in respuesta.content.decode()

    def test_500_propia(self, monkeypatch):
        def explota(request):
            raise RuntimeError("fallo inesperado")

        monkeypatch.setattr("analisis.views.render", lambda *a, **k: explota(None))
        respuesta = Client(raise_request_exception=False).get("/")
        assert respuesta.status_code == 500
        assert "Algo salió mal de nuestro lado" in respuesta.content.decode()


class TestLoggingSeguro:
    def test_un_error_del_llm_no_registra_el_cv(self, client, caplog, monkeypatch):
        call_command("cargar_vacantes_ejemplo")

        def falla(*args, **kwargs):
            raise ConexionLLMError("timeout")

        monkeypatch.setattr("analisis.views.analizar_cv", falla)
        with caplog.at_level(logging.INFO):
            client.post("/analizar/", {"texto_cv": TEXTO_CV, "texto_vacante": ""})
        assert "ConexionLLMError" in caplog.text
        assert FRAGMENTO_CV not in caplog.text.lower()

    def test_un_analisis_demo_completo_no_registra_el_cv(self, client, caplog):
        call_command("cargar_vacantes_ejemplo")
        with caplog.at_level(logging.DEBUG):
            client.post("/analizar/", {"texto_cv": TEXTO_CV, "texto_vacante": ""})
        assert "Agente: iteración" in caplog.text  # sí hay logs útiles
        assert FRAGMENTO_CV not in caplog.text.lower()
