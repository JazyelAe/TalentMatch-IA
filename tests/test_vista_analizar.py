"""Pruebas del formulario y la vista /analizar/ (T20). Corren en modo demo: sin API key."""

import os
from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from analisis.models import Analisis
from services.llm import ApiKeyInvalidaError, ConexionLLMError, LimiteApiError, RechazoModeloError, RespuestaInvalidaError
from services.orquestador import CatalogoVacioError
from tests.archivos_cv import TEXTO_CV, crear_docx, crear_pdf

pytestmark = pytest.mark.django_db
URL = "/analizar/"


@pytest.fixture
def catalogo():
    call_command("cargar_vacantes_ejemplo")


def enviar(client, **datos):
    return client.post(URL, {"texto_cv": "", "texto_vacante": "", **datos})


def test_get_muestra_el_formulario(client):
    respuesta = client.get(reverse("analisis:analizar"))
    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    assert 'enctype="multipart/form-data"' in html
    assert 'accept=".pdf,.docx"' in html


class TestExito:
    def test_con_pdf(self, client, catalogo):
        archivo = SimpleUploadedFile("cv.pdf", crear_pdf(TEXTO_CV.splitlines()), content_type="application/pdf")
        respuesta = enviar(client, archivo_cv=archivo)
        analisis = Analisis.objects.get()
        assert respuesta.status_code == 302
        assert respuesta.url == reverse("analisis:resultado", args=[analisis.pk])
        assert analisis.origen_cv == "pdf" and analisis.proveedor == "demo"

    def test_con_docx(self, client, catalogo):
        archivo = SimpleUploadedFile("cv.docx", crear_docx(TEXTO_CV.splitlines()))
        assert enviar(client, archivo_cv=archivo).status_code == 302
        assert Analisis.objects.get().origen_cv == "docx"

    def test_con_texto_y_vacante(self, client, catalogo):
        vacante = "Backend Python Jr\nRequisitos: Python, Django y FastAPI. Trabajo remoto.\nDeseable: Docker."
        respuesta = enviar(client, texto_cv=TEXTO_CV, texto_vacante=vacante)
        assert respuesta.status_code == 302
        assert Analisis.objects.get().resultado_externo() is not None

    def test_la_pagina_de_resultados_responde(self, client, catalogo):
        respuesta = enviar(client, texto_cv=TEXTO_CV)
        assert client.get(respuesta.url).status_code == 200


class TestErroresDelFormulario:
    def test_sin_archivo_ni_texto(self, client):
        respuesta = enviar(client)
        assert respuesta.status_code == 400
        assert "Sube tu CV en PDF o DOCX, o pega su texto." in respuesta.content.decode()

    def test_archivo_y_texto_a_la_vez(self, client, catalogo):
        archivo = SimpleUploadedFile("cv.pdf", crear_pdf(["x"]))
        respuesta = enviar(client, archivo_cv=archivo, texto_cv=TEXTO_CV)
        assert "Elige solo una opción" in respuesta.content.decode()
        assert Analisis.objects.count() == 0

    def test_extension_invalida(self, client, catalogo):
        respuesta = enviar(client, archivo_cv=SimpleUploadedFile("cv.txt", b"hola"))
        assert respuesta.status_code == 400
        assert "Formato no permitido" in respuesta.content.decode()

    def test_cv_muy_corto(self, client, catalogo):
        respuesta = enviar(client, texto_cv="Python y Django")
        assert "Prueba pegando el texto" in respuesta.content.decode()

    def test_vacante_muy_corta(self, client, catalogo):
        respuesta = enviar(client, texto_cv=TEXTO_CV, texto_vacante="Python")
        assert "vacante es muy corto" in respuesta.content.decode()
        assert Analisis.objects.count() == 0

    def test_archivo_mayor_a_5_mb(self, client, catalogo):
        archivo = SimpleUploadedFile("cv.pdf", b"0" * (5 * 1024 * 1024 + 10))
        respuesta = enviar(client, archivo_cv=archivo)
        assert "más de 5 MB" in respuesta.content.decode()

    def test_catalogo_vacio(self, client):
        respuesta = enviar(client, texto_cv=TEXTO_CV)
        assert "cargar_vacantes_ejemplo" in respuesta.content.decode()


@pytest.mark.parametrize("error", [ApiKeyInvalidaError, LimiteApiError, ConexionLLMError, RechazoModeloError, RespuestaInvalidaError])
def test_cada_error_del_llm_muestra_su_mensaje(client, catalogo, monkeypatch, error):
    def falla(*args, **kwargs):
        raise error("detalle técnico 123")

    monkeypatch.setattr("analisis.views.analizar_cv", falla)
    html = enviar(client, texto_cv=TEXTO_CV).content.decode()
    assert error.mensaje_usuario in html
    assert "detalle técnico 123" not in html  # la traza técnica nunca llega al usuario


def test_el_archivo_no_se_guarda(client, catalogo):
    """HU-01: el CV solo vive en memoria durante la petición."""
    assert settings.FILE_UPLOAD_HANDLERS == ["django.core.files.uploadhandler.MemoryFileUploadHandler"]
    contenido = crear_docx(TEXTO_CV.splitlines())
    enviar(client, archivo_cv=SimpleUploadedFile("cv-secreto-unico.docx", contenido))

    base = Path(settings.BASE_DIR)
    ignorar = {".venv", "node_modules", ".git"}
    for raiz, carpetas, archivos in os.walk(base):
        carpetas[:] = [c for c in carpetas if c not in ignorar]
        assert "cv-secreto-unico.docx" not in archivos
    assert not getattr(settings, "MEDIA_ROOT", "")  # el proyecto no tiene carpeta de subidas
    assert "cv-secreto-unico" not in str(list(Analisis.objects.values()))
