"""Pruebas de la extracción de texto del CV (T08)."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from services import extraccion
from services.extraccion import (
    ArchivoInvalidoError,
    CVDemasiadoLargoError,
    CVVacioError,
    extraer_texto,
    limpiar_texto,
)
from tests.archivos_cv import TEXTO_CV, crear_docx, crear_pdf


def subir(nombre: str, contenido: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(nombre, contenido)


class TestTextoPegado:
    def test_devuelve_el_texto_limpio(self):
        resultado = extraer_texto(texto="  " + TEXTO_CV + "\n\n\n\n  ")
        assert resultado.origen == "texto"
        assert resultado.texto == TEXTO_CV

    def test_sin_archivo_ni_texto(self):
        with pytest.raises(CVVacioError, match="Sube tu CV"):
            extraer_texto()

    def test_texto_en_blanco(self):
        with pytest.raises(CVVacioError):
            extraer_texto(texto="   \n  ")


class TestPdf:
    def test_extrae_texto_de_un_pdf(self):
        pdf = crear_pdf(TEXTO_CV.splitlines())
        resultado = extraer_texto(archivo=subir("cv.pdf", pdf))
        assert resultado.origen == "pdf"
        assert "Desarrolladora Python Jr" in resultado.texto
        assert "Django" in resultado.texto

    def test_extension_en_mayusculas(self):
        pdf = crear_pdf(TEXTO_CV.splitlines())
        assert extraer_texto(archivo=subir("CV.PDF", pdf)).origen == "pdf"

    def test_pdf_corrupto(self):
        with pytest.raises(ArchivoInvalidoError, match="dañado"):
            extraer_texto(archivo=subir("cv.pdf", b"%PDF-1.4 esto no es un pdf real"))

    def test_pdf_sin_texto_como_un_escaneo(self):
        with pytest.raises(CVVacioError, match="escaneada"):
            extraer_texto(archivo=subir("cv.pdf", crear_pdf([])))


class TestDocx:
    def test_extrae_parrafos(self):
        resultado = extraer_texto(archivo=subir("cv.docx", crear_docx(TEXTO_CV.splitlines())))
        assert resultado.origen == "docx"
        assert resultado.texto == TEXTO_CV

    def test_extrae_tambien_las_tablas(self):
        contenido = crear_docx(TEXTO_CV.splitlines(), tabla=[["Habilidad", "Nivel"], ["Kubernetes", "Básico"]])
        assert "Kubernetes | Básico" in extraer_texto(archivo=subir("cv.docx", contenido)).texto

    def test_docx_corrupto(self):
        with pytest.raises(ArchivoInvalidoError, match="DOCX"):
            extraer_texto(archivo=subir("cv.docx", b"no es un zip"))


class TestValidaciones:
    @pytest.mark.parametrize("nombre", ["cv.txt", "cv.doc", "cv.png", "cv", "cv.pdf.exe"])
    def test_extension_no_permitida(self, nombre):
        with pytest.raises(ArchivoInvalidoError, match="PDF o DOCX"):
            extraer_texto(archivo=subir(nombre, b"contenido"))

    def test_archivo_vacio(self):
        with pytest.raises(CVVacioError, match="vacío"):
            extraer_texto(archivo=subir("cv.pdf", b""))

    def test_archivo_mayor_a_5_mb(self):
        with pytest.raises(ArchivoInvalidoError, match="5 MB"):
            extraer_texto(archivo=subir("cv.pdf", b"0" * (5 * 1024 * 1024 + 1)))

    def test_archivo_sin_size_tambien_respeta_el_limite(self):
        archivo = io.BytesIO(b"0" * (5 * 1024 * 1024 + 1))
        archivo.name = "cv.pdf"
        with pytest.raises(ArchivoInvalidoError, match="5 MB"):
            extraer_texto(archivo=archivo)

    def test_texto_muy_corto(self):
        with pytest.raises(CVVacioError):
            extraer_texto(texto="Python, Django")

    def test_texto_demasiado_largo_no_se_recorta(self):
        with pytest.raises(CVDemasiadoLargoError, match="30,000"):
            extraer_texto(texto="a" * (extraccion.MAXIMO_CARACTERES + 1))

    def test_limites_exactos_se_aceptan(self):
        assert len(extraer_texto(texto="a" * extraccion.MINIMO_CARACTERES).texto) == 200
        assert len(extraer_texto(texto="a" * extraccion.MAXIMO_CARACTERES).texto) == 30_000

    def test_si_llegan_archivo_y_texto_gana_el_archivo(self):
        resultado = extraer_texto(archivo=subir("cv.docx", crear_docx(TEXTO_CV.splitlines())), texto="x" * 300)
        assert resultado.origen == "docx"


def test_limpiar_texto():
    assert limpiar_texto("  Hola   mundo \t\n\n\n\nAdiós\x00 ") == "Hola mundo\n\nAdiós"
