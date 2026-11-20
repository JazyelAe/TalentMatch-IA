"""Pruebas del historial de análisis (T22)."""

import pytest
from django.urls import reverse

from analisis.models import Analisis, ResultadoMatch
from tests.datos import perfil_valido

pytestmark = pytest.mark.django_db
URL = reverse("analisis:historial")


def crear(titulo_mejor: str | None = "Backend Jr", **cambios) -> Analisis:
    datos = {"origen_cv": "texto", "perfil": perfil_valido(), "recomendaciones": {}, "proveedor": "anthropic", "modelo": "m"}
    analisis = Analisis.objects.create(**{**datos, **cambios})
    if titulo_mejor:
        for posicion, (titulo, puntaje) in enumerate([(titulo_mejor, 81), ("Segunda", 60)], start=1):
            ResultadoMatch.objects.create(
                analisis=analisis, posicion=posicion, titulo=titulo, puntaje_determinista=0,
                puntaje_llm=0, puntaje_final=puntaje, explicacion="x",
            )
        ResultadoMatch.objects.create(
            analisis=analisis, es_externa=True, posicion=1, titulo="Externa", puntaje_determinista=0,
            puntaje_llm=0, puntaje_final=99, explicacion="x",
        )
    return analisis


def test_estado_vacio(client):
    html = client.get(URL).content.decode()
    assert "Todavía no hay análisis." in html


def test_muestra_fecha_nivel_mejor_vacante_y_puntaje(client):
    analisis = crear()
    html = client.get(URL).content.decode()
    assert f"Análisis #{analisis.pk}" in html
    assert ">jr<" in html
    assert "Backend Jr" in html and "81<span" in html
    assert "Externa" not in html  # la vacante pegada no cuenta como "mejor vacante"
    assert analisis.get_absolute_url() in html


def test_orden_del_mas_reciente_al_mas_antiguo(client):
    viejo, nuevo = crear("Vieja"), crear("Nueva")
    html = client.get(URL).content.decode()
    assert html.index("Nueva") < html.index("Vieja")


def test_paginacion(client):
    for i in range(11):
        crear(f"Vacante {i}")
    pagina1 = client.get(URL).content.decode()
    pagina2 = client.get(URL, {"pagina": 2}).content.decode()
    assert "Página 1 de 2" in pagina1 and "Vacante 10" in pagina1 and "Vacante 0" not in pagina1
    assert "Vacante 0" in pagina2


def test_pagina_invalida_muestra_la_primera(client):
    crear()
    assert client.get(URL, {"pagina": "abc"}).status_code == 200


def test_etiquetas_demo_y_parcial(client):
    crear(proveedor="demo", resultado_parcial=True)
    html = client.get(URL).content.decode()
    assert ">demo<" in html and ">parcial<" in html


def test_analisis_sin_resultados(client):
    crear(titulo_mejor=None)
    assert "Sin vacantes recomendadas" in client.get(URL).content.decode()


def test_no_hace_una_consulta_por_fila(client, django_assert_max_num_queries):
    for _ in range(10):
        crear()
    with django_assert_max_num_queries(4):
        client.get(URL)


def test_enlace_en_la_navegacion(client):
    assert f'href="{URL}"' in client.get("/").content.decode()
