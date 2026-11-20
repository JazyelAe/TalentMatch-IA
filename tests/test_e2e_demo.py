"""Prueba de punta a punta en modo demo (T24), como la viviría un reclutador sin API key:
cargar vacantes → subir un CV → ver resultados → encontrarlo en el historial.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from analisis.models import Analisis
from tests.archivos_cv import TEXTO_CV, crear_docx

pytestmark = pytest.mark.django_db


def test_flujo_completo_en_modo_demo(client):
    # 1. Carga del catálogo, como en el README.
    call_command("cargar_vacantes_ejemplo")

    # 2. La página de inicio lleva al formulario y avisa que está en modo demo.
    inicio = client.get("/").content.decode()
    assert 'href="/analizar/"' in inicio and "Modo demo:" in inicio

    # 3. Subir el CV en DOCX junto con una vacante pegada.
    vacante = "Backend Python Jr\nRequisitos: Python, Django y FastAPI. Trabajo remoto.\nDeseable: Docker."
    respuesta = client.post(
        "/analizar/",
        {"archivo_cv": SimpleUploadedFile("mi-cv.docx", crear_docx(TEXTO_CV.splitlines())), "texto_cv": "", "texto_vacante": vacante},
    )
    assert respuesta.status_code == 302
    analisis = Analisis.objects.get()

    # 4. La página de resultados muestra el top, la vacante pegada, las brechas y las sugerencias.
    resultados = client.get(respuesta.url).content.decode()
    assert "Tus mejores vacantes" in resultados
    assert analisis.mejor_resultado().titulo in resultados
    assert "La vacante que pegaste" in resultados
    assert "Qué te conviene aprender" in resultados
    assert "Cómo mejorar tu CV" in resultados
    assert 1 <= analisis.resultados_catalogo().count() <= 5
    assert not analisis.resultado_parcial  # el agente demo completa el ciclo de herramientas

    # 5. El análisis aparece en el historial con enlace a sus resultados.
    historial = client.get("/historial/").content.decode()
    assert f'href="{respuesta.url}"' in historial
