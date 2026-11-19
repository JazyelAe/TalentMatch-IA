"""Pruebas de la página de resultados (T21)."""

import pytest
from django.urls import reverse

from analisis.models import Analisis, ResultadoMatch
from tests.datos import perfil_valido, recomendaciones_validas
from vacantes.models import Vacante

pytestmark = pytest.mark.django_db


@pytest.fixture
def analisis():
    vacante = Vacante.objects.create(
        titulo="Backend Python Jr", empresa="Nubeterna (ficticia)", ubicacion="Guadalajara", modalidad="hibrido",
        nivel="jr", habilidades_requeridas=["Python", "Docker"], descripcion="(ficticia)",
    )
    rec = recomendaciones_validas()
    analisis = Analisis.objects.create(
        origen_cv="pdf", perfil=perfil_valido(),
        recomendaciones={k: rec[k] for k in ("brechas", "sugerencias_cv", "palabras_clave_ats")},
        proveedor="anthropic", modelo="claude-haiku-5-5", iteraciones_agente=3,
    )
    ResultadoMatch.objects.create(
        analisis=analisis, vacante=vacante, posicion=1, titulo=vacante.titulo, empresa=vacante.empresa,
        puntaje_determinista=50, puntaje_llm=80, puntaje_final=62, habilidades_coincidentes=["Python"],
        habilidades_faltantes=["Docker"], explicacion="Tu experiencia con Django encaja.",
    )
    return analisis


def ver(client, analisis):
    respuesta = client.get(reverse("analisis:resultado", args=[analisis.pk]))
    return respuesta, respuesta.content.decode()


def test_muestra_perfil_top_brechas_y_sugerencias(client, analisis):
    respuesta, html = ver(client, analisis)
    assert respuesta.status_code == 200
    for texto in [
        "Tu perfil", "Desarrolladora backend con un año",  # perfil
        "Backend Python Jr", "Nubeterna (ficticia)", "Guadalajara", "Híbrido",  # vacante
        "62<span", "Habilidades: 50 · Evaluación IA: 80", "Tu experiencia con Django encaja.",  # puntaje y explicación
        "Qué te conviene aprender", "Prioridad alta", "Dockeriza un proyecto propio", "2 semanas",  # brechas
        "Cuantifica tus logros.", "APIs REST",  # CV y ATS
    ]:
        assert texto in html, texto
    assert 'style="width: 62%"' in html


def test_404_si_no_existe(client):
    assert client.get(reverse("analisis:resultado", args=[999])).status_code == 404


def test_aviso_de_resultado_parcial(client, analisis):
    assert "Resultado parcial" not in ver(client, analisis)[1]
    analisis.resultado_parcial = True
    analisis.save()
    assert "Resultado parcial" in ver(client, analisis)[1]


def test_aviso_de_modo_demo(client, analisis):
    assert "modo demo</strong>" not in ver(client, analisis)[1]
    analisis.proveedor = "demo"
    analisis.save()
    assert "modo demo</strong>" in ver(client, analisis)[1]


def test_seccion_de_vacante_externa(client, analisis):
    assert "La vacante que pegaste" not in ver(client, analisis)[1]
    ResultadoMatch.objects.create(
        analisis=analisis, es_externa=True, posicion=1, titulo="Vacante Real X", empresa="",
        puntaje_determinista=40, puntaje_llm=50, puntaje_final=44, explicacion="Te falta FastAPI.",
    )
    html = ver(client, analisis)[1]
    assert "La vacante que pegaste" in html and "Vacante Real X" in html and "Empresa no indicada" in html


def test_resultado_con_vacante_borrada_sigue_mostrandose(client, analisis):
    Vacante.objects.all().delete()
    respuesta, html = ver(client, analisis)
    assert respuesta.status_code == 200 and "Backend Python Jr" in html


@pytest.mark.parametrize("puntaje, categoria", [(85, "alto"), (70, "alto"), (50, "medio"), (20, "bajo")])
def test_categoria_del_puntaje(puntaje, categoria):
    assert ResultadoMatch(puntaje_final=puntaje).categoria == categoria
